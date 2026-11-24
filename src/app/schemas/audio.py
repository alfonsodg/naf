"""Audio asset and speech synthesis schemas."""

from pydantic import BaseModel


class AudioAssetMetadata(BaseModel):
    """Metadata required to persist and serve a generated audio asset."""

    digest_id: str
    filename: str
    format: str = "mp3"
    duration_seconds: float
    size_bytes: int
    checksum: str
    provider: str
    voice: str | None = None
    version: str = "1.0"


class AudioSegment(BaseModel):
    """One synthesized speech segment.

    ``audio_bytes`` holds mono 16-bit little-endian PCM at ``sample_rate``; the
    storage layer frames the concatenated segments into one WAV file.
    """

    text: str
    audio_bytes: bytes
    duration_seconds: float
    index: int
    sample_rate: int = 24_000


class TTSConfig(BaseModel):
    """Speech synthesis parameters for Spanish reports."""

    provider: str
    voice: str | None = None
    speed: float = 1.0
    language: str
    segment_pause_ms: int = 500
