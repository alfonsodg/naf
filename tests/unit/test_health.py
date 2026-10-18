"""Health and readiness endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import health

client = TestClient(app)


def test_liveness_does_not_touch_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness answers even when every dependency is down."""

    class ExplodingEngine:
        def connect(self) -> Any:
            raise AssertionError("liveness must not open a database connection")

    async def exploding_health(self: Any) -> dict[str, str]:
        raise AssertionError("liveness must not call the reader")

    monkeypatch.setattr(health, "engine", ExplodingEngine())
    monkeypatch.setattr(health.MinifluxClient, "health", exploding_health)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_every_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Readiness names each dependency it checks."""

    class OkConnection:
        def __enter__(self) -> "OkConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, statement: object) -> None:
            return None

    class OkEngine:
        def connect(self) -> OkConnection:
            return OkConnection()

    async def ok_health(self: Any) -> dict[str, str]:
        return {"status": "OK"}

    monkeypatch.setattr(health, "engine", OkEngine())
    monkeypatch.setattr(health.MinifluxClient, "health", ok_health)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["miniflux"]["status"] == "ok"


def test_readiness_returns_503_when_database_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing dependency degrades readiness and reports which one."""

    class BrokenEngine:
        def connect(self) -> Any:
            raise RuntimeError("connection refused")

    async def ok_health(self: Any) -> dict[str, str]:
        return {"status": "OK"}

    monkeypatch.setattr(health, "engine", BrokenEngine())
    monkeypatch.setattr(health.MinifluxClient, "health", ok_health)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == {"status": "error", "error": "RuntimeError"}
    assert body["checks"]["miniflux"]["status"] == "ok"


def test_readiness_returns_503_when_reader_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reader outage also degrades readiness."""
    from app.core.exceptions import MinifluxAPIError

    class OkConnection:
        def __enter__(self) -> "OkConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, statement: object) -> None:
            return None

    class OkEngine:
        def connect(self) -> OkConnection:
            return OkConnection()

    async def broken_health(self: Any) -> dict[str, str]:
        raise MinifluxAPIError("reader down")

    monkeypatch.setattr(health, "engine", OkEngine())
    monkeypatch.setattr(health.MinifluxClient, "health", broken_health)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["miniflux"]["status"] == "error"
