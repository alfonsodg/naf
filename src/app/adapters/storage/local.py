"""Local filesystem audio storage adapter."""

import hashlib
from pathlib import Path

import aiofiles

from app.core.config import settings
from app.core.ports.storage import AudioStorage
from app.schemas.audio import AudioAssetMetadata


class LocalAudioStorage(AudioStorage):
    """Store generated audio on the local filesystem."""

    def __init__(self, base_path: str | None = None) -> None:
        """Create the storage root if it does not exist."""
        self.base_path = Path(base_path or settings.audio_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str:
        """Persist the audio file and return its path."""
        metadata.checksum = hashlib.sha256(audio_bytes).hexdigest()
        file_path = self.base_path / metadata.filename
        async with aiofiles.open(file_path, "wb") as handle:
            await handle.write(audio_bytes)
        return str(file_path)

    async def retrieve(self, asset_id: str) -> bytes:
        """Read a stored audio file."""
        async with aiofiles.open(Path(asset_id), "rb") as handle:
            data: bytes = await handle.read()
        return data

    async def get_url(self, asset_id: str) -> str | None:
        """Return a public URL when a base URL is configured."""
        if settings.audio_base_url:
            return f"{settings.audio_base_url}/{Path(asset_id).name}"
        return asset_id

    async def delete(self, asset_id: str) -> bool:
        """Remove a stored audio file if present."""
        try:
            Path(asset_id).unlink(missing_ok=True)
        except OSError:
            return False
        return True
