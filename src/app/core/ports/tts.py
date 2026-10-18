"""Text-to-speech port."""

from abc import ABC, abstractmethod

from app.schemas.audio import AudioSegment, TTSConfig


class TTSProvider(ABC):
    """Synthesize Spanish speech segments."""

    @abstractmethod
    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment:
        """Synthesize one text segment."""

    @abstractmethod
    async def synthesize_batch(self, texts: list[str], config: TTSConfig) -> list[AudioSegment]:
        """Synthesize several segments preserving input order."""

    @abstractmethod
    def supports_segmentation(self) -> bool:
        """Report whether the provider accepts pre-split text."""
