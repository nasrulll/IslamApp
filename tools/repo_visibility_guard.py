"""Fail-closed safety layer for switching the repository between private and public.

Uses only the standard library so the CI job needs no dependency install.
Findings never contain the matched secret value.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_POLICY = "data/repo-visibility-policy.json"
MAX_SCAN_BYTES = 2 * 1024 * 1024
ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")
TOKEN = re.compile(r"[a-z0-9]+")
WORKFLOW_GLOBS = (".github/workflows/*.yml", ".github/workflows/*.yaml")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    detail: str


def resolve_visibility(cli: str | None, env: Mapping[str, str]) -> tuple[str, str]:
    """Return (effective mode, source). Unknown visibility is treated as public."""
    value, source = None, "unknown (fail-closed)"
    if cli in ("private", "public"):
        value, source = cli, "--visibility"
    elif env.get("REPO_VISIBILITY") in ("private", "public"):
        value, source = env["REPO_VISIBILITY"], "REPO_VISIBILITY"
    elif env.get("REPO_PRIVATE", "").lower() in ("true", "false"):
        value = "private" if env["REPO_PRIVATE"].lower() == "true" else "public"
        source = "REPO_PRIVATE"
    if value is None:
        value = "public"
    if value == "private" and env.get("FORCE_PUBLIC_RULES", "").lower() == "true":
        return "public", "FORCE_PUBLIC_RULES (strict pre-flight while private)"
    return value, source


def load_policy(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8", errors="replace")
    return [p for p in out.split("\0") if p]


def matches(path: str, globs: list[str]) -> bool:
    base = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g) for g in globs)


def check_path(path: str, policy: dict, public: bool) -> Finding | None:
    if matches(path, policy["allowed_path_globs"]):
        return None
    if matches(path, policy["forbidden_path_globs"]):
        return Finding("forbidden-path", path, "file type or location must never be committed")
    if public and matches(path, policy["public_only"]["forbidden_path_globs"]):
        return Finding("public-forbidden-path", path, "book/document file must not be public")
    return None


def read_text(root: Path, rel: str) -> str | None:
    full = root / rel
    try:
        if not full.is_file() or full.is_symlink() or full.stat().st_size > MAX_SCAN_BYTES:
            return None
        data = full.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def secret_findings(text: str, path: str, policy: dict) -> list[Finding]:
    return [
        Finding("secret-pattern", path, f"{name} pattern matched (value withheld)")
        for name, pattern in policy["secret_patterns"].items()
        if re.search(pattern, text)
    ]


def trace_count(text: str, policy: dict) -> int:
    """Distinct tokens revealing where source data is hosted; terms are only stored hashed."""
    hashes = set(policy["public_only"]["source_trace_token_sha256"])
    return sum(hashlib.sha256(tok.encode()).hexdigest() in hashes for tok in set(TOKEN.findall(text.lower())))


def trace_finding(text: str, path: str, policy: dict, suffix: str = "") -> Finding | None:
    count = trace_count(text, policy)
    if not count:
        return None
    return Finding("public-source-trace", path, f"{count} term(s) reveal the data source host{suffix}")


def on_block(text: str) -> str:
    match = re.search(r"^on:[^\n]*\n(?:(?:[ \t].*|#.*|)\n)*", text + "\n", re.MULTILINE)
    return match.group(0) if match else ""


def trigger_names(block: str) -> set[str]:
    """Event names under `on:`; over-inclusive for inline maps, which fails closed."""
    lines = block.splitlines()
    if not lines:
        return set()
    inline = lines[0].split(":", 1)[1].split("#", 1)[0]
    names = set(re.findall(r"[A-Za-z_]+", inline))
    children = [line for line in lines[1:] if line.strip() and not line.lstrip().startswith("#")]
    if children:
        base = min(len(line) - len(line.lstrip()) for line in children)
        for line in children:
            match = re.match(r"\s*([A-Za-z_]+)\s*:", line)
            if match and len(line) - len(line.lstrip()) == base:
                names.add(match.group(1))
    return names


def step_block(lines: list[str], idx: int) -> str:
    def indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    start = idx
    while start > 0 and not (
        lines[start].lstrip().startswith("- ") and indent(lines[start]) <= indent(lines[idx])
    ):
        start -= 1
    base = indent(lines[start])
    end = idx + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and (indent(line) < base or (indent(line) == base and line.lstrip().startswith("- "))):
            break
        end += 1
    return "\n".join(lines[start:end])


def is_private_guarded(block: str, marker: str) -> bool:
    for line in block.splitlines():
        if re.match(r"\s*(?:- )?if:", line) and marker in line:
            return not re.search(r"!\s*github|==\s*['\"]?false|!=\s*['\"]?true", line)
    return False


def workflow_findings(text: str, name: str, policy: dict, public: bool) -> list[Finding]:
    path = f".github/workflows/{name}"
    found: list[Finding] = []
    triggers = on_block(text)
    for trigger in policy["forbidden_workflow_triggers"]:
        if re.search(rf"\b{re.escape(trigger)}\b", triggers):
            found.append(Finding("workflow-trigger", path, f"{trigger} exposes secrets to untrusted code"))
    if not public:
        return found
    rules = policy["public_only"]
    if re.search(r"secrets\.(?!GITHUB_TOKEN\b)\w+", text):
        outside = sorted(trigger_names(triggers) - set(rules["secret_workflow_allowed_triggers"]))
        if outside:
            found.append(Finding("workflow-secret-trigger", path,
                                 f"secret-using workflow can be started by others via: {', '.join(outside)}"))
    if not re.search(r"^permissions:", text, re.MULTILINE):
        found.append(Finding("workflow-permissions-missing", path, "declare least-privilege top-level permissions"))
    if "write-all" in text:
        found.append(Finding("workflow-permissions-broad", path, "write-all token permissions"))
    for action in re.findall(r"^\s*(?:- )?uses:\s*['\"]?([^\s'\"#]+)", text, re.MULTILINE):
        trusted = action.startswith(("./", "actions/")) or re.search(r"@[0-9a-f]{40}$", action)
        if not trusted:
            found.append(Finding("workflow-unpinned-action", path,
                                 f"third-party action {action} must be pinned to a full commit SHA"))
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "actions/upload-artifact" not in line:
            continue
        block = step_block(lines, idx)
        if is_private_guarded(block, rules["private_guard_marker"]):
            continue
        labels = re.findall(r"^\s+(?:path|name):\s*(.+)$", block, re.MULTILINE)
        words = [w for w in rules["restricted_artifact_words"] if any(w in x.lower() for x in labels)]
        if words:
            found.append(Finding("public-artifact-restricted", path,
                                 f"artifact looks restricted ({', '.join(words)}) and is not private-only"))
        elif name not in rules["artifact_workflow_allowlist"]:
            found.append(Finding("public-artifact-unreviewed", path,
                                 "artifact upload not in reviewed aggregate-only allowlist"))
    return found


def scan_tree(root: Path, policy: dict, public: bool) -> list[Finding]:
    found: list[Finding] = []
    rules = policy["public_only"]
    for rel in tracked_files(root):
        hit = check_path(rel, policy, public)
        if hit:
            found.append(hit)
        text = read_text(root, rel)
        trace = trace_finding(rel + "\n" + (text or ""), rel, policy) if public else None
        if trace:
            found.append(trace)
        if public and (root / rel).is_file() and (root / rel).stat().st_size > rules["max_file_bytes"]:
            found.append(Finding("public-large-file", rel, "file exceeds the public size limit"))
        if text is None:
            continue
        found.extend(secret_findings(text, rel, policy))
        arabic_checked = public and not matches(rel, rules["arabic_allowed_path_globs"])
        if arabic_checked and len(ARABIC.findall(text)) > rules["max_arabic_chars_per_file"]:
            found.append(Finding("public-arabic-bulk", rel, "possible book text; review rights before public"))
        if any(fnmatch.fnmatch(rel, g) for g in WORKFLOW_GLOBS):
            found.extend(workflow_findings(text, rel.rsplit("/", 1)[-1], policy, public))
    return found


def scan_history(root: Path, policy: dict, public: bool) -> list[Finding]:
    """Everything ever committed becomes public with the repository."""
    found: dict[tuple[str, str], Finding] = {}
    # Names are listed separately: binary files have no "+++ b/" line in a patch.
    names = subprocess.run(
        ["git", "log", "--all", "--no-renames", "--diff-filter=AM", "--name-only", "-z", "--pretty=format:"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8", errors="replace")
    for name in {n.strip("\n") for n in names.split("\0") if n.strip("\n")}:
        for hit in (check_path(name, policy, public), public and trace_finding(name, name, policy)):
            if hit:
                found[(hit.rule, name)] = Finding(hit.rule, name, hit.detail + " (in history)")
    cmd = ["git", "log", "--all", "-p", "-U0", "--no-color", "--no-renames", "--diff-filter=AM", "--pretty=format:"]
    current = "(unknown)"
    with subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, text=True, errors="replace") as proc:
        for line in proc.stdout or []:
            if line.startswith("+++ b/"):
                current = line[6:].strip()
            elif line.startswith("+") and not line.startswith("+++"):
                for hit in secret_findings(line, current, policy):
                    found[(hit.rule, current + hit.detail)] = Finding(hit.rule, current, hit.detail + " (in history)")
                if public and (trace := trace_finding(line, current, policy, " (in history)")):
                    found.setdefault((trace.rule, current), trace)
    if public:
        for label, args in (("(commit messages)", ["log", "--all", "--format=%B"]),
                            ("(ref names)", ["for-each-ref", "--format=%(refname)"])):
            out = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            trace = trace_finding(out.stdout.decode("utf-8", errors="replace"), label, policy)
            if trace:
                found[(trace.rule, label)] = trace
    return list(found.values())


def run_guard(root: Path, public: bool, policy: dict, history: bool = False) -> list[Finding]:
    found = scan_tree(root, policy, public)
    if history:
        found.extend(scan_history(root, policy, public))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visibility", choices=("private", "public"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--history", action="store_true", help="also scan every commit")
    args = parser.parse_args(argv)
    mode, source = resolve_visibility(args.visibility, os.environ)
    try:
        policy = load_policy(args.policy or args.root / DEFAULT_POLICY)
        findings = run_guard(args.root, mode == "public", policy, args.history)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Visibility guard could not run: {exc}", file=sys.stderr)
        return 2
    print(f"Visibility guard mode: {mode} (source: {source})")
    for item in findings:
        print(f"FAIL [{item.rule}] {item.path}: {item.detail}")
    if findings:
        print(f"{len(findings)} finding(s). Do not publish or merge until resolved.")
        return 1
    print("Visibility guard PASS. This is a safety net, not a rights or legal clearance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
