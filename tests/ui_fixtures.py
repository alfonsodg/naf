"""Doubles and factories for the server-rendered page tests.

Nothing here is collected by pytest: the module only keeps the fakes and the
stored fixtures that the page tests share, so the test module stays focused on
the routes and the rendered HTML.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AudioAsset, Digest, DigestStory
from app.schemas.audio import AudioAssetMetadata, AudioSegment, TTSConfig
from app.schemas.digest import Citation
from app.schemas.digest import Digest as GeneratedDigest
from app.schemas.digest import DigestStory as GeneratedStory

SEGMENTS = [
    {
        "index": 0,
        "story_index": 0,
        "start_seconds": 0.0,
        "end_seconds": 4.5,
        "text": "Introducción a la primera historia.",
    },
    {
        "index": 1,
        "story_index": 0,
        "start_seconds": 4.5,
        "end_seconds": 9.0,
        "text": "Detalle de la primera historia.",
    },
    {
        "index": 2,
        "story_index": 1,
        "start_seconds": 9.0,
        "end_seconds": 13.0,
        "text": "Texto de la segunda historia.",
    },
]


def settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_model": "report-model",
        "tts_model_path": "/models/kokoro.onnx",
        "tts_voices_path": "/models/voices.bin",
        **overrides,
    }
    return Settings(**base)


def entry(entry_id: int, published: str) -> dict[str, Any]:
    """Build one normalized entry with its provenance."""
    return {
        "entry_id": entry_id,
        "url": f"https://example.test/{entry_id}",
        "title": f"Entrada {entry_id}",
        "published_at": published,
        "feed_id": 1,
        "feed_title": "Alpha",
    }


class FakeReader:
    """Reader double that serves entries and feeds, and can fail on demand."""

    def __init__(self, entries: list[dict[str, Any]] | None = None, feeds: list[dict[str, Any]] | None = None) -> None:
        self.entries = entries or []
        self.feeds = feeds or []
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def get_entries_page(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        """Return the configured entries, recording the filters."""
        self.calls.append(kwargs)
        return list(self.entries), len(self.entries)

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return the configured feeds or raise the configured failure."""
        if self.error is not None:
            raise self.error
        return list(self.feeds)


class FakeGenerator:
    """Generator double that cites the first selected entry."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def generate(
        self,
        entries: list[dict[str, Any]],
        filters: dict[str, Any],
        since_last: str | None = None,
    ) -> GeneratedDigest:
        """Build one story that cites the first entry."""
        self.calls.append({"entries": entries, "filters": filters, "since_last": since_last})
        if self.error is not None:
            raise self.error
        first = entries[0]
        return GeneratedDigest(
            title="Radar semanal",
            summary="Resumen del periodo seleccionado.",
            period_start="2026-11-18T00:00:00+00:00",
            period_end="2026-11-24T00:00:00+00:00",
            stories=[
                GeneratedStory(
                    title="Historia del periodo",
                    summary="Resumen en español con atribución.",
                    claims=["La entrada publica una novedad."],
                    citations=[Citation(entry_id=str(first["entry_id"]), entry_url=first["url"], title=first["title"])],
                    pub_type="news",
                )
            ],
        )

    def validate_citations(self, digest: GeneratedDigest, entries: list[dict[str, Any]]) -> bool:
        """Accept every generated citation."""
        return True


class FakeTTS:
    """Speech engine double that can fail on demand."""

    def __init__(self) -> None:
        self.error: Exception | None = None

    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment:
        """Synthesize one segment with deterministic PCM."""
        return self._segments([text])[0]

    async def synthesize_batch(self, texts: list[str], config: TTSConfig) -> list[AudioSegment]:
        """Synthesize every text or raise the configured failure."""
        if self.error is not None:
            raise self.error
        return self._segments(texts)

    def supports_segmentation(self) -> bool:
        """Declare that the caller owns the segmentation."""
        return True

    def _segments(self, texts: list[str]) -> list[AudioSegment]:
        """Render each text as mono 16-bit PCM."""
        return [
            AudioSegment(
                text=text,
                audio_bytes=b"\x00\x00" * 240,
                duration_seconds=0.01,
                index=index,
                sample_rate=24_000,
            )
            for index, text in enumerate(texts)
        ]


class FakeStorage:
    """Storage double that keeps the written bytes in memory."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        """Keep the bytes under the asset file name and return that name."""
        self.files[metadata.filename] = audio_bytes
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


def make_report(
    session: Session,
    status: str = "ready",
    with_audio: bool = False,
) -> Digest:
    """Store one report with two cited stories, optionally with its audio."""
    digest = Digest(
        title="Radar semanal",
        summary="Resumen del periodo seleccionado.",
        period_start=datetime(2026, 11, 18),
        period_end=datetime(2026, 11, 24),
        filters={"since_last": False, "search": "modelo", "tags": ["ai"], "max_entries": 5},
        entry_ids=[1, 2],
        version="1.0",
        meta={"model": "report-model", "entry_count": 2},
        status=status,
    )
    if status == "ready":
        digest.stories = [
            DigestStory(
                title="Historia uno",
                summary="Explicación de la primera historia.",
                claims=["Primera afirmación."],
                citations=[
                    {
                        "entry_id": "1",
                        "entry_url": "https://example.test/uno",
                        "title": "Fuente uno",
                        "author": "Autora",
                    }
                ],
                pub_type="news",
                order_index=0,
            ),
            DigestStory(
                title="Historia dos",
                summary="Explicación de la segunda historia.",
                claims=["Segunda afirmación."],
                citations=[
                    {
                        "entry_id": "2",
                        "entry_url": "https://example.test/dos",
                        "title": "Fuente dos",
                        "author": None,
                    }
                ],
                pub_type="release",
                order_index=1,
            ),
        ]
    session.add(digest)
    session.commit()
    if with_audio:
        asset = AudioAsset(
            digest_id=digest.id,
            filename="report.wav",
            file_path="report.wav",
            format="wav",
            duration_seconds=75.0,
            size_bytes=2048,
            provider="test",
            voice="es",
            version="1.0",
        )
        digest.has_audio = True
        session.add(asset)
        session.commit()
    return digest


def report_form() -> dict[str, str]:
    """Return a valid creation form."""
    return {
        "period_start": "2026-11-18T00:00",
        "period_end": "2026-11-24T00:00",
        "max_entries": "5",
        "tags": "ai, modelos",
        "search": "modelo",
    }
