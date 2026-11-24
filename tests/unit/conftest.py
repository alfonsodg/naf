"""Fixtures for the audio suite: a SQLite session, a fake engine, and a fake store.

The optional Kokoro package, its model files, and the filesystem never enter
these tests: deterministic PCM and an in-memory store stand in for both, so the
service and the HTTP contract are exercised on their own.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.ports.storage import AudioStorage
from app.core.ports.tts import TTSProvider
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Digest, DigestStory
from app.routers import reports
from app.schemas.audio import AudioAssetMetadata, AudioSegment, TTSConfig

SAMPLE_RATE = 24_000
SAMPLES_PER_CHAR = 24
PROVIDER = "kokoro-onnx"


def _settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "tts_model_path": "/models/kokoro-v1.0.onnx",
        "tts_voices_path": "/models/voices-v1.0.bin",
        **overrides,
    }
    return Settings(**base)


class _FakeTTS(TTSProvider):
    """Speech engine double: deterministic PCM and a recorded batch call."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.configs: list[TTSConfig] = []
        self.error: Exception | None = None

    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment:
        """Synthesize one segment as the batch path does."""
        return self._segments([text], config)[0]

    async def synthesize_batch(self, texts: list[str], config: TTSConfig) -> list[AudioSegment]:
        """Record the batch and return one segment per text."""
        self.batches.append(list(texts))
        self.configs.append(config)
        if self.error is not None:
            raise self.error
        return self._segments(texts, config)

    def supports_segmentation(self) -> bool:
        """Declare that the caller owns the segmentation."""
        return True

    def _segments(self, texts: list[str], config: TTSConfig) -> list[AudioSegment]:
        """Render each text as deterministic mono 16-bit PCM."""
        salt = len(self.batches)
        return [
            AudioSegment(
                text=text,
                audio_bytes=bytes([salt % 256, 0]) * (len(text) * SAMPLES_PER_CHAR),
                duration_seconds=(len(text) * SAMPLES_PER_CHAR) / SAMPLE_RATE,
                index=index,
                sample_rate=SAMPLE_RATE,
            )
            for index, text in enumerate(texts)
        ]


class _FakeStorage(AudioStorage):
    """Storage double that keeps the written bytes in memory."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.metadata: list[AudioAssetMetadata] = []
        self.calls = 0

    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        """Keep the bytes under the asset file name and return that name."""
        self.calls += 1
        self.files[metadata.filename] = audio_bytes
        self.metadata.append(metadata)
        return metadata.filename

    async def retrieve(self, asset_id: str) -> bytes:
        """Return the stored bytes."""
        return self.files[asset_id]

    async def get_url(self, asset_id: str) -> str | None:
        """Report that the fake has no public URL."""
        return None

    async def delete(self, asset_id: str) -> bool:
        """Remove one stored file."""
        return self.files.pop(asset_id, None) is not None


@dataclass
class Wiring:
    """Fake halves plus the function that reconfigures the routes."""

    tts: _FakeTTS
    storage: _FakeStorage
    configure: Callable[..., None]


@pytest.fixture
def audio_session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the API."""
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
def audio_wiring(monkeypatch: pytest.MonkeyPatch) -> Wiring:
    """Replace the speech engine, the storage, and the settings the routes build."""
    tts = _FakeTTS()
    storage = _FakeStorage()

    def _configure(**overrides: Any) -> None:
        monkeypatch.setattr(reports, "_tts", lambda: tts)
        monkeypatch.setattr(reports, "_audio_storage", lambda: storage)
        monkeypatch.setattr(reports, "app_settings", _settings(**overrides))

    _configure()
    return Wiring(tts=tts, storage=storage, configure=_configure)


def make_digest(session: Session, status: str = "ready") -> Digest:
    """Store one report with two stories, or one that cannot be voiced."""
    digest = Digest(
        title="Radar semanal",
        summary="Resumen del periodo seleccionado.",
        period_start=datetime(2026, 11, 18),
        period_end=datetime(2026, 11, 24),
        filters={},
        entry_ids=[1, 2],
        version="1.0",
        meta={},
        status=status,
    )
    if status == "ready":
        digest.stories = [
            DigestStory(
                title="Historia uno",
                summary="Explicación de la primera historia.",
                claims=["Primera afirmación.", "Segunda afirmación."],
                citations=[],
                pub_type="news",
                order_index=0,
            ),
            DigestStory(
                title="Historia dos",
                summary="Explicación de la segunda historia.",
                claims=["Tercera afirmación."],
                citations=[],
                pub_type="release",
                order_index=1,
            ),
        ]
    session.add(digest)
    session.commit()
    return digest


@pytest.fixture
def audio_digest(audio_session: Session) -> Callable[..., Digest]:
    """Return a factory that stores one report in the test database."""

    def _make(status: str = "ready") -> Digest:
        return make_digest(audio_session, status)

    return _make
