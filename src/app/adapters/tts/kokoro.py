"""Kokoro ONNX speech synthesis.

The optional engine is imported on first use: the API starts without the
package, the model, or the voices bundle, and the audio routes answer 503 until
the deployment configures both files. Synthesis is blocking, so every engine
call runs on a worker thread and the event loop stays free.
"""

import asyncio
import sys
from array import array
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.exceptions import TTSError
from app.core.ports.tts import TTSProvider
from app.schemas.audio import AudioSegment, TTSConfig

DEFAULT_VOICE = "ef_dora"
DEFAULT_LANGUAGE = "es"
DEFAULT_SAMPLE_RATE = 24_000


class KokoroTTS(TTSProvider):
    """Synthesize Spanish speech segments with the Kokoro ONNX engine."""

    def __init__(self, settings: Settings, engine: Any = None) -> None:
        """Bind the adapter to one configuration without loading the engine.

        ``engine`` is a test seam: production always leaves it empty and lets
        the first synthesis load the optional package.
        """
        self._settings = settings
        self._engine = engine

    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment:
        """Synthesize one segment on a worker thread."""
        return await self._synthesize(text, config, 0)

    async def synthesize_batch(self, texts: list[str], config: TTSConfig) -> list[AudioSegment]:
        """Synthesize every segment in order.

        The engine is loaded once and called sequentially: it is not documented
        as thread-safe, and request cost is dominated by the model itself.
        """
        return [await self._synthesize(text, config, index) for index, text in enumerate(texts)]

    def supports_segmentation(self) -> bool:
        """Report that the engine accepts text already split by the caller."""
        return True

    async def _synthesize(self, text: str, config: TTSConfig, index: int) -> AudioSegment:
        """Run one blocking synthesis and project its samples as a segment."""
        if not text.strip():
            raise TTSError("the speech engine received an empty segment")
        pcm, sample_rate = await asyncio.to_thread(self._render, text, config)
        return AudioSegment(
            text=text,
            audio_bytes=pcm,
            duration_seconds=len(pcm) / (2 * sample_rate),
            index=index,
            sample_rate=sample_rate,
        )

    def _render(self, text: str, config: TTSConfig) -> tuple[bytes, int]:
        """Call the engine and convert its float samples to 16-bit PCM.

        Engine failures are translated to a fixed reason: exception text from
        the engine can carry the configured model path, which never reaches the
        caller.
        """
        engine = self._load_engine()
        voice = config.voice or self._settings.tts_voice or DEFAULT_VOICE
        language = _language(config.language)
        try:
            samples, sample_rate = engine.create(
                text,
                voice=voice,
                speed=config.speed,
                lang=language,
            )
        except Exception as exc:
            raise TTSError("the speech engine could not synthesize the segment") from exc
        return _pcm16(samples), int(sample_rate or DEFAULT_SAMPLE_RATE)

    def _load_engine(self) -> Any:
        """Load the engine once, refusing to guess a missing model or voices file."""
        if self._engine is not None:
            return self._engine
        model_path, voices_path = self._configured_paths()
        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise TTSError("the speech engine is not installed") from exc
        try:
            self._engine = Kokoro(str(model_path), str(voices_path))
        except Exception as exc:
            raise TTSError("the speech engine could not load its model") from exc
        return self._engine

    def _configured_paths(self) -> tuple[Path, Path]:
        """Validate that the deployment configured two readable files."""
        model = self._settings.tts_model_path.strip()
        voices = self._settings.tts_voices_path.strip()
        if not model or not voices:
            raise TTSError("speech synthesis is not configured")
        model_path = Path(model)
        voices_path = Path(voices)
        if not model_path.is_file() or not voices_path.is_file():
            raise TTSError("the configured speech assets are missing")
        return model_path, voices_path


def _language(tag: str) -> str:
    """Map a BCP-47 tag to the language prefix the engine expects."""
    return tag.split("-", 1)[0].strip().lower() or DEFAULT_LANGUAGE


def _pcm16(samples: Any) -> bytes:
    """Convert the engine's float samples in [-1, 1] to signed 16-bit PCM."""
    values = array("h", (int(max(-1.0, min(1.0, float(sample))) * 32767.0) for sample in samples))
    if sys.byteorder == "big":
        values.byteswap()
    return values.tobytes()
