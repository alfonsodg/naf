"""The Kokoro adapter contract, exercised with an injected engine.

The optional package, the ONNX model, and the voices bundle never load here:
the engine seam returns deterministic samples, so the float-to-PCM conversion,
the ordering, the metadata, and the failure translation are tested on their own.
"""

import struct
from typing import Any

import pytest

from app.adapters.tts.kokoro import KokoroTTS
from app.core.config import Settings
from app.core.exceptions import TTSError
from app.schemas.audio import TTSConfig


def _settings(**overrides: Any) -> Settings:
    """Build settings with paths a test can point wherever it needs."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "tts_model_path": "/models/kokoro-v1.0.onnx",
        "tts_voices_path": "/models/voices-v1.0.bin",
        **overrides,
    }
    return Settings(**base)


def _config() -> TTSConfig:
    """Build the speech parameters the service forwards."""
    return TTSConfig(provider="kokoro-onnx", voice="em_alex", speed=1.2, language="es-ES")


class _Engine:
    """Engine double that records calls and returns fixed samples."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def create(self, text: str, **kwargs: Any) -> tuple[list[float], int]:
        """Return four samples covering the clipping boundaries."""
        self.calls.append({"text": text, **kwargs})
        if self.error is not None:
            raise self.error
        return [0.0, 0.5, -0.5, 1.0], 24_000


async def test_the_samples_become_signed_pcm_with_the_engine_rate() -> None:
    """Float samples are clipped and converted to little-endian 16-bit PCM."""
    engine = _Engine()
    adapter = KokoroTTS(_settings(), engine)

    segment = await adapter.synthesize_segment("Hola.", _config())

    assert struct.unpack("<4h", segment.audio_bytes) == (0, 16383, -16383, 32767)
    assert segment.sample_rate == 24_000
    assert segment.duration_seconds == pytest.approx(4 / 24_000)
    assert segment.index == 0
    assert engine.calls[0] == {"text": "Hola.", "voice": "em_alex", "speed": 1.2, "lang": "es"}


async def test_a_batch_keeps_the_input_order_and_indices() -> None:
    """Every text is synthesized once, in order, with its position."""
    engine = _Engine()
    adapter = KokoroTTS(_settings(), engine)

    segments = await adapter.synthesize_batch(["Uno.", "Dos."], _config())

    assert [segment.text for segment in segments] == ["Uno.", "Dos."]
    assert [segment.index for segment in segments] == [0, 1]
    assert [call["text"] for call in engine.calls] == ["Uno.", "Dos."]


def test_the_adapter_accepts_pre_split_text() -> None:
    """The service owns the segmentation, so the provider declares support."""
    assert KokoroTTS(_settings()).supports_segmentation() is True


async def test_an_unconfigured_engine_is_refused() -> None:
    """Empty paths fail before the optional package or the files are touched."""
    adapter = KokoroTTS(_settings(tts_model_path="", tts_voices_path=""))

    with pytest.raises(TTSError, match="not configured"):
        await adapter.synthesize_segment("Hola.", _config())


async def test_a_missing_file_is_refused() -> None:
    """A configured path that does not exist never reaches the package import."""
    settings = _settings(tts_model_path="/models/absent.onnx", tts_voices_path="/models/absent.bin")

    with pytest.raises(TTSError, match="missing"):
        await KokoroTTS(settings).synthesize_segment("Hola.", _config())


async def test_an_empty_segment_is_refused() -> None:
    """Blank text is a caller mistake, not an engine call."""
    engine = _Engine()

    with pytest.raises(TTSError, match="empty"):
        await KokoroTTS(_settings(), engine).synthesize_segment("   ", _config())

    assert engine.calls == []


async def test_an_engine_failure_does_not_leak_its_detail() -> None:
    """The engine reason can carry a model path, so only a generic reason escapes."""
    engine = _Engine()
    engine.error = RuntimeError("cannot open /secret/kokoro.onnx")

    with pytest.raises(TTSError) as caught:
        await KokoroTTS(_settings(), engine).synthesize_segment("Hola.", _config())

    assert "/secret" not in str(caught.value)
    assert "could not synthesize" in str(caught.value)
