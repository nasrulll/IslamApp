import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.repo_visibility_guard import (
    load_policy,
    main,
    resolve_visibility,
    run_guard,
    trace_count,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = load_policy(ROOT / "data" / "repo-visibility-policy.json")
HUB_TOKEN = "h" + "f_" + "A" * 34  # built at runtime: no token literal and no source-host term
ARABIC_BULK = "كتاب" * 1200
# Rule tests use a self-contained policy: the real allowlist and the real source-host
# terms (only stored hashed) are deployment-specific and differ in each repository.
TEST_POLICY = {**POLICY, "public_only": {**POLICY["public_only"],
                "artifact_workflow_allowlist": ["reviewed-example.yml"]}}
TRACE_POLICY = {**TEST_POLICY, "public_only": {**TEST_POLICY["public_only"],
                "source_trace_token_sha256": [hashlib.sha256(b"examplehost").hexdigest()]}}

PERMS = "permissions:\n  contents: read\n"

PR_SECRET_WORKFLOW = """name: x
on:
  pull_request:
permissions:
  contents: read
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo
        env:
          DATA_TOKEN: ${{ secrets.DATA_TOKEN }}
"""


def artifact_workflow(path: str, name: str, guard: str = "") -> str:
    return f"""name: x
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo
      - name: Upload something
{guard}        uses: actions/upload-artifact@v4
        with:
          name: {name}
          path: {path}
"""


class TempRepo:
    def __init__(self, files: dict[str, str]):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.git("init", "-q")
        self.write(files)

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.test", "-c", "user.name=t", *args],
            cwd=self.root, check=True, capture_output=True,
        )

    def write(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", "-A")

    def rules(self, public: bool, history: bool = False) -> set[str]:
        return {f.rule for f in run_guard(self.root, public, TEST_POLICY, history)}


class VisibilityResolutionTests(unittest.TestCase):
    def test_cli_wins_over_environment(self):
        self.assertEqual(resolve_visibility("private", {"REPO_PRIVATE": "false"})[0], "private")

    def test_repo_private_flag_maps_to_mode(self):
        self.assertEqual(resolve_visibility(None, {"REPO_PRIVATE": "true"})[0], "private")
        self.assertEqual(resolve_visibility(None, {"REPO_PRIVATE": "false"})[0], "public")

    def test_unknown_or_missing_visibility_is_public(self):
        self.assertEqual(resolve_visibility(None, {})[0], "public")
        self.assertEqual(resolve_visibility(None, {"REPO_PRIVATE": "maybe"})[0], "public")
        self.assertEqual(resolve_visibility(None, {"REPO_VISIBILITY": "internal"})[0], "public")

    def test_force_public_rules_upgrades_private_only(self):
        env = {"REPO_PRIVATE": "true", "FORCE_PUBLIC_RULES": "true"}
        self.assertEqual(resolve_visibility(None, env)[0], "public")
        env = {"REPO_PRIVATE": "false", "FORCE_PUBLIC_RULES": "false"}
        self.assertEqual(resolve_visibility(None, env)[0], "public")


class TreeScanTests(unittest.TestCase):
    def test_clean_repo_passes_in_both_modes(self):
        repo = TempRepo({"README.md": "hello", "src/a.py": "print(1)\n"})
        self.assertEqual(repo.rules(False), set())
        self.assertEqual(repo.rules(True), set())

    def test_forbidden_paths_fail_even_when_private(self):
        for rel in (".env", "keys/server.pem", "d/book.parquet", "audit-output/a.json", "x/pages.jsonl"):
            with self.subTest(rel=rel):
                self.assertIn("forbidden-path", TempRepo({rel: "x"}).rules(False))

    def test_more_credential_and_archive_files_fail_even_when_private(self):
        for rel in (".netrc", "deploy/service-account-prod.json", "infra/terraform.tfstate", "backup/corpus.zip"):
            with self.subTest(rel=rel):
                self.assertIn("forbidden-path", TempRepo({rel: "x"}).rules(False))

    def test_book_and_document_files_are_blocked_only_when_public(self):
        for rel in ("kitab/fathul-bari.pdf", "out/book.epub", "data/pages-all.jsonl", "data/books.csv"):
            with self.subTest(rel=rel):
                repo = TempRepo({rel: "x"})
                self.assertEqual(repo.rules(False), set())
                self.assertEqual(repo.rules(True), {"public-forbidden-path"})

    def test_additional_secret_formats_are_detected(self):
        samples = {
            "npmrc": "//registry.npmjs.org/:_authToken=" + "n" * 36,
            "db": "DATABASE_URL=postgresql://app:" + "s3cretpass" + "@db.example.com/prod",
            "slack": "xoxb-" + "1" * 12 + "-abcdefghij",
            "pgp": "-----BEGIN PGP PRIVATE " + "KEY BLOCK-----",
        }
        for label, text in samples.items():
            with self.subTest(label=label):
                self.assertEqual(TempRepo({"cfg.txt": text}).rules(False), {"secret-pattern"})

    def test_local_development_database_url_is_not_a_secret(self):
        text = "postgresql://dev:" + "devpass" + "@localhost:5432/fikihmu"
        self.assertEqual(TempRepo({"cfg.txt": text}).rules(True), set())

    def test_env_example_is_allowed(self):
        self.assertEqual(TempRepo({".env.example": "DATA_TOKEN=\n"}).rules(False), set())

    def test_secret_fails_in_private_mode_and_value_is_withheld(self):
        repo = TempRepo({"notes.txt": f"token {HUB_TOKEN}\n"})
        findings = run_guard(repo.root, False, POLICY)
        self.assertEqual({f.rule for f in findings}, {"secret-pattern"})
        self.assertNotIn(HUB_TOKEN, " ".join(f"{f.path} {f.detail}" for f in findings))

    def test_size_and_arabic_limits_apply_only_when_public(self):
        repo = TempRepo({"big.txt": "a" * (POLICY["public_only"]["max_file_bytes"] + 1),
                         "docs/book.md": ARABIC_BULK})
        self.assertEqual(repo.rules(False), set())
        self.assertEqual(repo.rules(True), {"public-large-file", "public-arabic-bulk"})

    def test_arabic_fixture_directory_is_allowed(self):
        self.assertEqual(TempRepo({"tests/fixtures/sample.txt": ARABIC_BULK}).rules(True), set())


class WorkflowTests(unittest.TestCase):
    def wf(self, text: str, name: str = "w.yml") -> TempRepo:
        return TempRepo({f".github/workflows/{name}": text})

    def test_pull_request_target_is_forbidden_in_every_mode(self):
        repo = self.wf("name: x\non:\n  pull_request_target:\njobs: {}\n")
        self.assertEqual(repo.rules(False), {"workflow-trigger"})

    def test_secret_workflow_on_pull_request_fails_only_when_public(self):
        repo = self.wf(PR_SECRET_WORKFLOW)
        self.assertEqual(repo.rules(False), set())
        self.assertEqual(repo.rules(True), {"workflow-secret-trigger"})

    def test_secret_workflow_triggerable_by_outsiders_fails_when_public(self):
        for trigger in ("issue_comment", "issues", "pull_request_review_comment", "fork"):
            with self.subTest(trigger=trigger):
                repo = self.wf(PR_SECRET_WORKFLOW.replace("pull_request:", f"{trigger}:"))
                self.assertEqual(repo.rules(True), {"workflow-secret-trigger"})

    def test_secret_workflow_on_owner_only_triggers_passes(self):
        text = PR_SECRET_WORKFLOW.replace("  pull_request:", "  push:\n    branches: [main]\n  workflow_dispatch:")
        self.assertEqual(self.wf(text).rules(True), set())

    def test_inline_trigger_list_is_parsed(self):
        text = PR_SECRET_WORKFLOW.replace("on:\n  pull_request:", "on: [push, issue_comment]")
        self.assertEqual(self.wf(text).rules(True), {"workflow-secret-trigger"})

    def test_token_permissions_must_be_declared_and_narrow(self):
        base = "name: x\non:\n  push:\njobs: {}\n"
        self.assertEqual(self.wf(base).rules(True), {"workflow-permissions-missing"})
        self.assertEqual(self.wf(base).rules(False), set())
        self.assertEqual(self.wf(base + "permissions: write-all\n").rules(True), {"workflow-permissions-broad"})

    def test_third_party_actions_must_be_pinned_when_public(self):
        def steps(uses: str) -> str:
            return f"name: x\non:\n  push:\n{PERMS}jobs:\n  j:\n    steps:\n      - uses: {uses}\n"
        self.assertEqual(self.wf(steps("someone/action@v1")).rules(True), {"workflow-unpinned-action"})
        self.assertEqual(self.wf(steps("someone/action@v1")).rules(False), set())
        self.assertEqual(self.wf(steps("someone/action@" + "a" * 40)).rules(True), set())
        self.assertEqual(self.wf(steps("actions/checkout@v4")).rules(True), set())

    def test_restricted_artifact_blocked_unless_private_guarded(self):
        text = artifact_workflow("audit-output/restricted-review/", "internal-queue")
        self.assertEqual(self.wf(text, "reviewed-example.yml").rules(True),
                         {"public-artifact-restricted"})
        guarded = artifact_workflow("audit-output/restricted-review/", "internal-queue",
                                    "        if: ${{ success() && github.event.repository.private }}\n")
        self.assertEqual(self.wf(guarded, "reviewed-example.yml").rules(True), set())

    def test_negated_private_guard_does_not_count(self):
        guard = "        if: ${{ !github.event.repository.private }}\n"
        text = artifact_workflow("out/internal/", "internal-queue", guard)
        self.assertEqual(self.wf(text).rules(True), {"public-artifact-restricted"})

    def test_aggregate_artifact_only_passes_in_allowlisted_workflow(self):
        text = artifact_workflow("audit-output/summary.json", "aggregate-counts")
        self.assertEqual(self.wf(text, "reviewed-example.yml").rules(True), set())
        self.assertEqual(self.wf(text, "new-unreviewed.yml").rules(True), {"public-artifact-unreviewed"})
        self.assertEqual(self.wf(text, "new-unreviewed.yml").rules(False), set())


class HistoryTests(unittest.TestCase):
    def test_secret_removed_from_tree_is_still_found_in_history(self):
        repo = TempRepo({"notes.txt": f"token {HUB_TOKEN}\n"})
        repo.git("commit", "-q", "-m", "add")
        repo.write({"notes.txt": "clean\n"})
        repo.git("commit", "-q", "-m", "remove")
        self.assertEqual(repo.rules(False), set())
        self.assertEqual(repo.rules(False, history=True), {"secret-pattern"})

    def test_binary_forbidden_file_is_found_in_history(self):
        repo = TempRepo({})
        (repo.root / "book.parquet").write_bytes(b"PAR1\0\x01binary")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "add")
        repo.git("rm", "-q", "book.parquet")
        repo.git("commit", "-q", "-m", "remove")
        self.assertEqual(repo.rules(True, history=True), {"forbidden-path"})

    def test_rename_to_forbidden_name_is_found_in_history(self):
        repo = TempRepo({"config.txt": "x"})
        repo.git("commit", "-q", "-m", "add")
        repo.git("mv", "config.txt", ".env")
        repo.git("commit", "-q", "-m", "rename")
        repo.git("rm", "-q", ".env")
        repo.git("commit", "-q", "-m", "remove")
        self.assertEqual(repo.rules(True, history=True), {"forbidden-path"})

    def test_public_only_document_in_history_is_found_when_public(self):
        repo = TempRepo({"kitab.pdf": "x"})
        repo.git("commit", "-q", "-m", "add")
        repo.git("rm", "-q", "kitab.pdf")
        repo.git("commit", "-q", "-m", "remove")
        self.assertEqual(repo.rules(False, history=True), set())
        self.assertEqual(repo.rules(True, history=True), {"public-forbidden-path"})

    def test_forbidden_file_deleted_later_is_found_in_history(self):
        repo = TempRepo({"data/book.parquet": "x"})
        repo.git("commit", "-q", "-m", "add")
        repo.git("rm", "-q", "data/book.parquet")
        repo.git("commit", "-q", "-m", "remove")
        self.assertEqual(repo.rules(True), set())
        self.assertEqual(repo.rules(True, history=True), {"forbidden-path"})


class CommandLineTests(unittest.TestCase):
    def test_exit_codes(self):
        policy = str(ROOT / "data" / "repo-visibility-policy.json")
        clean = TempRepo({"README.md": "ok"})
        dirty = TempRepo({".env": "x"})
        self.assertEqual(main(["--root", str(clean.root), "--policy", policy, "--visibility", "public"]), 0)
        self.assertEqual(main(["--root", str(dirty.root), "--policy", policy, "--visibility", "private"]), 1)
        self.assertEqual(main(["--root", str(clean.root), "--policy", str(clean.root / "missing.json")]), 2)

    def test_this_repository_passes_private_and_only_source_traces_block_public(self):
        self.assertEqual(run_guard(ROOT, False, POLICY), [])
        self.assertLessEqual({f.rule for f in run_guard(ROOT, True, POLICY)},
                             {"public-source-trace", "public-artifact-unreviewed"})

    def test_guard_components_carry_no_source_trace(self):
        for rel in ("data/repo-visibility-policy.json", "tools/repo_visibility_guard.py",
                    "tests/test_repo_visibility_guard.py", ".githooks/pre-push",
                    ".github/workflows/visibility-guard.yml", "docs/architecture/REPO-VISIBILITY-GUARD.md"):
            if not (ROOT / rel).is_file():  # e.g. docs are not part of the clean public export
                continue
            with self.subTest(rel=rel):
                self.assertEqual(trace_count(rel + "\n" + (ROOT / rel).read_text(encoding="utf-8"), POLICY), 0)


class SourceTraceTests(unittest.TestCase):
    TERM = "examplehost"

    def rules(self, repo: TempRepo, public: bool, history: bool = False) -> list:
        return run_guard(repo.root, public, TRACE_POLICY, history)

    def test_trace_in_content_or_path_blocks_only_public(self):
        for files in ({"docs/a.md": "Source data lives on ExampleHost datasets."},
                      {"tools/examplehost_fetch.py": "print(1)\n"}):
            with self.subTest(files=files):
                repo = TempRepo(files)
                self.assertEqual(self.rules(repo, False), [])
                found = self.rules(repo, True)
                self.assertEqual({f.rule for f in found}, {"public-source-trace"})
                self.assertNotIn(self.TERM, " ".join(f.detail for f in found).lower())

    def test_term_inside_a_longer_word_is_not_a_trace(self):
        self.assertEqual(self.rules(TempRepo({"a.md": "myexamplehostname"}), True), [])

    def test_removed_trace_commit_message_and_branch_are_found_in_history(self):
        repo = TempRepo({"a.md": "from examplehost"})
        repo.git("commit", "-q", "-m", "add data from ExampleHost")
        repo.git("branch", "examplehost-sync")
        repo.write({"a.md": "clean"})
        repo.git("commit", "-q", "-m", "clean")
        self.assertEqual(self.rules(repo, True), [])
        paths = {f.path for f in self.rules(repo, True, history=True)}
        self.assertEqual(paths, {"a.md", "(commit messages)", "(ref names)"})


if __name__ == "__main__":
    unittest.main()
