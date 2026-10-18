from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class AudioAssetMetadata(BaseModel):
    digest_id: str
    filename: str
    format: str = "mp3"
    duration_seconds: float
    size_bytes: int
    checksum: str
    provider: str
    voice: Optional[str] = None
    version: str = "1.0"


class AudioStorage(ABC):
    @abstractmethod
    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        pass

    @abstractmethod
    async def retrieve(self, asset_id: str) -> bytes:
        pass

    @abstractmethod
    async def get_url(self, asset_id: str) -> Optional[str]:
        pass

    @abstractmethod
    async def delete(self, asset_id: str) -> bool:
        pass
