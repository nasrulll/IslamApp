"""Contract tests for deliberately limited, non-production Fikihmu API."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_PATH = Path(__file__).resolve().parents[1] / "services/api/app/main.py"
spec = importlib.util.spec_from_file_location("fikihmu_bootstrap_main", API_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_health_and_process_only_readiness() -> None:
    with TestClient(module.build_app()) as client:
        assert client.get("/health/live").json() == {
            "status": "ok", "service": "fikihmu-api"
        }
        assert client.get("/health/ready").json() == {
            "status": "ready", "scope": "process-only", "checked_dependencies": False
        }


def test_platform_discloses_unimplemented_services() -> None:
    with TestClient(module.build_app()) as client:
        response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["blueprint"] == "1.1-LOCKED"
    assert body["verified_corpus_available"] is False
    assert body["ai_available"] is False
    assert [item["slug"] for item in body["services"]] == [
        "fikih", "sanad-kitab", "tafsir-ayat"
    ]
    assert all(item["status"] == "planned" for item in body["services"])


def test_openapi_contains_expected_read_only_paths() -> None:
    with TestClient(module.build_app()) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert set(paths) == {"/health/live", "/health/ready", "/api/v1/meta"}
        assert all(set(methods.keys()) == {"get"} for methods in paths.values())
        assert client.get("/api/v1/fiqh/answer").status_code == 404


def test_production_hides_documentation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIKIHMU_ENV", "production")
    with TestClient(module.build_app()) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/health/live").status_code == 200


def test_invalid_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIKIHMU_ENV", "unsafe")
    with pytest.raises(ValueError, match="FIKIHMU_ENV"):
        module.build_app()


def test_wildcard_cors_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIKIHMU_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="Wildcard CORS"):
        module.build_app()


def test_cors_only_allows_explicit_development_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIKIHMU_ENV", raising=False)
    monkeypatch.delenv("FIKIHMU_CORS_ORIGINS", raising=False)
    with TestClient(module.build_app()) as client:
        allowed = client.get("/api/v1/meta", headers={"Origin": "http://localhost:3000"})
        denied = client.get("/api/v1/meta", headers={"Origin": "https://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers
