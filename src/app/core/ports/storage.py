"""Audio storage port."""

from abc import ABC, abstractmethod

from app.schemas.audio import AudioAssetMetadata


class AudioStorage(ABC):
    """Persist and serve generated audio assets."""

    @abstractmethod
    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        """Persist audio and return its asset identifier."""

    @abstractmethod
    async def retrieve(self, asset_id: str) -> bytes:
        """Return the stored audio bytes."""

    @abstractmethod
    async def get_url(self, asset_id: str) -> str | None:
        """Return a public URL when the backend supports one."""

    @abstractmethod
    async def delete(self, asset_id: str) -> bool:
        """Remove an asset; return False when it does not exist."""
