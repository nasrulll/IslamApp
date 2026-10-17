"""Fikihmu HTTP bootstrap: limited API only; no live corpus or AI endpoints."""
import os
from typing import Literal, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "fikihmu-api"


class Readiness(BaseModel):
    status: Literal["ready"] = "ready"
    scope: str = "process-only"
    checked_dependencies: bool = False


class Service(BaseModel):
    slug: str
    status: Literal["planned"] = "planned"


class PlatformMeta(BaseModel):
    platform: str = "Fikihmu"
    blueprint: str = "1.1-LOCKED"
    phase: str = "bootstrap"
    verified_corpus_available: bool = False
    ai_available: bool = False
    services: list[Service]


def read_environment() -> Literal["development", "staging", "production"]:
    value = os.environ.get("FIKIHMU_ENV", "development").strip().lower()
    if value not in {"development", "staging", "production"}:
        raise ValueError("FIKIHMU_ENV must be development, staging, or production")
    return cast(Literal["development", "staging", "production"], value)


def build_app() -> FastAPI:
    environment = read_environment()
    expose_docs = environment != "production"
    api = FastAPI(
        title="Fikihmu API",
        version="0.0.0",
        description="Bootstrap API only: no verified corpus or active AI endpoints.",
        docs_url="/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    configured = os.environ.get("FIKIHMU_CORS_ORIGINS", "").strip()
    if configured:
        origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    elif environment == "development":
        origins = ["http://localhost:3000", "http://localhost:3001"]
    else:
        origins = []
    if "*" in origins:
        raise ValueError("Wildcard CORS is forbidden for Fikihmu")
    if any(not origin.startswith(("https://", "http://")) for origin in origins):
        raise ValueError("CORS origins must be explicit http(s) origins")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @api.get("/health/live", response_model=Health, tags=["health"])
    def liveness() -> Health:
        return Health()

    @api.get("/health/ready", response_model=Readiness, tags=["health"])
    def readiness() -> Readiness:
        # This deliberately checks ONLY the API process, not external services.
        return Readiness()

    @api.get("/api/v1/meta", response_model=PlatformMeta, tags=["platform"])
    def platform_meta() -> PlatformMeta:
        return PlatformMeta(services=[
            Service(slug="fikih"),
            Service(slug="sanad-kitab"),
            Service(slug="tafsir-ayat"),
        ])

    return api


app = build_app()
