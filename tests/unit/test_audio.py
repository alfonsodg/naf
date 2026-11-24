"""The audio pipeline: synthesis, storage, the project detail, and the served WAV.

The fake engine and storage live in this suite's conftest. These tests cover the
HTTP contract: a ready edition is voiced once, a forced request makes a second
immutable asset, and an edition that is not ready or cannot reach an engine is
refused without side effects.
"""

import hashlib
import io
import wave
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import TTSError
from app.main import app
from app.models import AudioAsset, Digest
from app.services.audio import MAX_SEGMENT_CHARS

client = TestClient(app)

SAMPLE_RATE = 24_000
SAMPLES_PER_CHAR = 24
PROVIDER = "kokoro-onnx"


def _post(report_id: int, **params: Any) -> Any:
    """Ask for the spoken edition of one report."""
    return client.post(f"/api/v1/reports/{report_id}/audio", params=params)


def test_a_ready_report_is_synthesized_and_stored(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """One batch is synthesized, stored once, and recorded against the edition."""
    digest = audio_digest()

    response = _post(digest.id)

    assert response.status_code == 201
    asset = response.json()["data"]
    assert asset["asset_id"] >= 1
    assert asset["filename"].endswith(".wav")
    assert asset["duration_seconds"] > 0
    assert asset["size_bytes"] == len(audio_wiring.storage.files[asset["filename"]])
    assert asset["provider"] == PROVIDER
    assert asset["voice"] == "ef_dora"
    assert asset["created_at"] is not None
    assert audio_wiring.storage.calls == 1
    metadata = audio_wiring.storage.metadata[0]
    assert metadata.format == "wav"
    assert metadata.provider == PROVIDER
    assert metadata.version == "1.0"
    assert metadata.digest_id == str(digest.id)
    assert metadata.checksum == hashlib.sha256(audio_wiring.storage.files[asset["filename"]]).hexdigest()
    assert len(audio_wiring.tts.batches) == 1
    assert all(len(text) <= MAX_SEGMENT_CHARS for text in audio_wiring.tts.batches[0])
    assert audio_wiring.tts.configs[0].language == "es-ES"
    audio_session.refresh(digest)
    assert digest.has_audio is True
    rows = audio_session.execute(select(AudioAsset).where(AudioAsset.digest_id == digest.id)).scalars().all()
    assert [row.id for row in rows] == [asset["asset_id"]]


def test_a_second_request_returns_the_stored_asset(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """Only an explicit force synthesizes again."""
    digest = audio_digest()
    first = _post(digest.id).json()["data"]

    second = _post(digest.id).json()["data"]

    assert second["asset_id"] == first["asset_id"]
    assert len(audio_wiring.tts.batches) == 1
    assert audio_wiring.storage.calls == 1


def test_force_regenerates_and_records_a_second_asset(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """A forced synthesis is a new immutable artifact, not an overwrite."""
    digest = audio_digest()
    first = _post(digest.id).json()["data"]

    second = _post(digest.id, force=True).json()["data"]

    assert second["asset_id"] != first["asset_id"]
    assert len(audio_wiring.tts.batches) == 2
    rows = audio_session.execute(select(AudioAsset).where(AudioAsset.digest_id == digest.id)).scalars().all()
    assert len(rows) == 2


@pytest.mark.parametrize("status", ["no_news", "failed"])
def test_a_report_that_is_not_ready_is_refused(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest], status: str
) -> None:
    """A placeholder or failed edition owns no report text to read aloud."""
    digest = audio_digest(status)

    response = _post(digest.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "REPORT_NOT_READY"
    assert audio_wiring.tts.batches == []
    assert audio_wiring.storage.calls == 0
    audio_session.refresh(digest)
    assert digest.has_audio is False


@pytest.mark.parametrize("missing", ["tts_model_path", "tts_voices_path"])
def test_an_unconfigured_engine_is_refused_before_any_work(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest], missing: str
) -> None:
    """An empty model or voices path answers 503 without touching the report."""
    digest = audio_digest()
    audio_wiring.configure(**{missing: ""})

    response = _post(digest.id)

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "TTS_NOT_CONFIGURED"
    assert audio_wiring.tts.batches == []
    assert audio_wiring.storage.calls == 0
    assert audio_session.execute(select(AudioAsset)).scalars().all() == []
    audio_session.refresh(digest)
    assert digest.has_audio is False


def test_the_detail_lists_the_stored_asset(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """The report projection carries the audio metadata and the flag."""
    digest = audio_digest()
    before = client.get(f"/api/v1/reports/{digest.id}").json()["data"]
    asset = _post(digest.id).json()["data"]

    after = client.get(f"/api/v1/reports/{digest.id}").json()["data"]

    assert before["audio"] == []
    assert after["has_audio"] is True
    assert [row["asset_id"] for row in after["audio"]] == [asset["asset_id"]]
    assert after["audio"][0]["filename"] == asset["filename"]
    assert after["audio"][0]["duration_seconds"] == asset["duration_seconds"]
    assert after["audio"][0]["voice"] == "ef_dora"


def test_the_stored_file_is_a_valid_wav(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """The header, the frame count, the duration, and the size all agree."""
    digest = audio_digest()
    asset = _post(digest.id).json()["data"]
    data = audio_wiring.storage.files[asset["filename"]]

    with wave.open(io.BytesIO(data), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == SAMPLE_RATE
        frames = handle.getnframes()

    expected = sum(len(text) * SAMPLES_PER_CHAR for text in audio_wiring.tts.batches[0])
    assert frames == expected
    assert asset["duration_seconds"] == pytest.approx(frames / SAMPLE_RATE, abs=0.001)
    assert asset["size_bytes"] == len(data)


def test_the_audio_is_served_as_a_named_wav(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """GET returns the stored bytes with the WAV media type and file name."""
    digest = audio_digest()
    asset = _post(digest.id).json()["data"]

    response = client.get(f"/api/v1/reports/{digest.id}/audio")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert asset["filename"] in response.headers["content-disposition"]
    assert response.content == audio_wiring.storage.files[asset["filename"]]


def test_audio_is_not_found_before_generation(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """A report without an asset answers 404 in the documented envelope."""
    digest = audio_digest()

    response = client.get(f"/api/v1/reports/{digest.id}/audio")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "AUDIO_NOT_FOUND"


def test_an_unknown_report_is_not_found(audio_session: Session, audio_wiring: Any) -> None:
    """The audio routes refuse an unknown edition before reading anything."""
    assert client.get("/api/v1/reports/999/audio").status_code == 404
    assert _post(999).status_code == 404
    assert audio_wiring.tts.batches == []


def test_a_synthesis_failure_leaves_the_text_report_available(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """A failing engine answers 502, stores nothing, and keeps the edition ready."""
    digest = audio_digest()
    audio_wiring.tts.error = TTSError("the model at /models/kokoro-v1.0.onnx could not load")

    response = _post(digest.id)

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "TTS_SYNTHESIS_FAILED"
    assert "/models" not in response.text
    assert audio_wiring.storage.calls == 0
    audio_session.refresh(digest)
    assert digest.has_audio is False
    detail = client.get(f"/api/v1/reports/{digest.id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["audio"] == []
