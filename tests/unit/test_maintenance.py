"""Edition cleanup: preview, dry run, and the guarded deletion."""

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.ports.storage import AudioStorage
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import AudioAsset, Digest
from app.routers import maintenance
from app.schemas.audio import AudioAssetMetadata

client = TestClient(app)


class FakeStorage(AudioStorage):
    """In-memory audio backend that records deletions."""

    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.files: dict[str, bytes] = {}

    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        self.files[metadata.filename] = audio_bytes
        return metadata.filename

    async def retrieve(self, asset_id: str) -> bytes:
        return self.files[asset_id]

    async def get_url(self, asset_id: str) -> str | None:
        return asset_id

    async def delete(self, asset_id: str) -> bool:
        self.deleted.append(asset_id)
        return self.files.pop(asset_id, None) is not None


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    opened = factory()
    app.dependency_overrides[get_session] = lambda: opened
    try:
        yield opened
    finally:
        app.dependency_overrides.clear()
        opened.close()
        engine.dispose()


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """Replace the audio backend the route builds."""
    fake = FakeStorage()
    monkeypatch.setattr(maintenance, "LocalAudioStorage", lambda: fake)
    return fake


def _edition(session: Session, created: datetime, *, audio: bool = False) -> Digest:
    """Store one edition, optionally with an audio asset."""
    digest = Digest(title="Informe", summary="", filters={}, created_at=created, status="ready")
    session.add(digest)
    session.commit()
    if audio:
        asset = AudioAsset(
            digest_id=digest.id,
            filename=f"report-{digest.id}.wav",
            file_path=f"report-{digest.id}.wav",
            format="wav",
            duration_seconds=10.0,
            size_bytes=2048,
            provider="test",
        )
        session.add(asset)
        session.commit()
    return digest


def test_the_preview_lists_only_editions_older_than_the_window(session: Session, storage: FakeStorage) -> None:
    """A recent edition is never proposed for deletion."""
    old = _edition(session, datetime.utcnow() - timedelta(days=120), audio=True)
    recent = _edition(session, datetime.utcnow() - timedelta(days=10), audio=True)

    body = client.get("/api/v1/maintenance/editions", params={"days": 90}).json()["data"]

    assert body["editions"] == [old.id]
    assert recent.id not in body["editions"]
    assert body["bytes"] == 2048
    assert body["filenames"] == [f"report-{old.id}.wav"]


def test_a_dry_run_deletes_nothing(session: Session, storage: FakeStorage) -> None:
    """The default call reports the deletion without performing it."""
    _edition(session, datetime.utcnow() - timedelta(days=120), audio=True)

    body = client.post("/api/v1/maintenance/editions", params={"days": 90}).json()["data"]

    assert body["dry_run"] is True
    assert body["deleted_editions"] == 0
    assert storage.deleted == []
    assert session.query(Digest).count() == 1


def test_the_cleanup_removes_old_editions_and_their_audio(session: Session, storage: FakeStorage) -> None:
    """Only the old edition and its file disappear."""
    old = _edition(session, datetime.utcnow() - timedelta(days=120), audio=True)
    recent = _edition(session, datetime.utcnow() - timedelta(days=10), audio=True)
    storage.files[f"report-{old.id}.wav"] = b"old"

    body = client.post("/api/v1/maintenance/editions", params={"days": 90, "dry_run": "false"}).json()["data"]

    assert body["dry_run"] is False
    assert body["deleted_editions"] == 1
    assert body["deleted_bytes"] == 2048
    assert storage.deleted == [f"report-{old.id}.wav"]
    assert [digest.id for digest in session.query(Digest).all()] == [recent.id]


def test_a_missing_file_is_counted_and_does_not_block(session: Session, storage: FakeStorage) -> None:
    """A file already gone is reported, not fatal."""
    _edition(session, datetime.utcnow() - timedelta(days=120), audio=True)

    body = client.post("/api/v1/maintenance/editions", params={"days": 90, "dry_run": "false"}).json()["data"]

    assert body["missing_files"] == 1
    assert body["deleted_editions"] == 1
    assert all(isinstance(path, str) for path in storage.deleted)


def test_the_window_is_validated(session: Session, storage: FakeStorage) -> None:
    """Zero or an excessive window is refused at the boundary."""
    assert client.get("/api/v1/maintenance/editions", params={"days": 0}).status_code == 422
    assert client.get("/api/v1/maintenance/editions", params={"days": 4000}).status_code == 422
