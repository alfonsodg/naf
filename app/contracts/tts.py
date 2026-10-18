from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel


class AudioSegment(BaseModel):
    text: str
    audio_bytes: bytes
    duration_seconds: float
    index: int


class TTSConfig(BaseModel):
    provider: str = "podcastfy"
    voice: Optional[str] = None
    speed: float = 1.0
    language: str = "es-ES"
    segment_pause_ms: int = 500


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment:
        pass

    @abstractmethod
    async def synthesize_batch(
        self, texts: List[str], config: TTSConfig
    ) -> List[AudioSegment]:
        pass

    @abstractmethod
    def supports_segmentation(self) -> bool:
        pass
