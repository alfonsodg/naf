"""The local audio storage adapter."""

from pathlib import Path

import pytest

from app.adapters.storage.local import LocalAudioStorage
from app.schemas.audio import AudioAssetMetadata


def _metadata(name: str = "report-1.wav") -> AudioAssetMetadata:
    """Build the metadata the audio service passes to the store."""
    return AudioAssetMetadata(
        digest_id="1",
        filename=name,
        format="wav",
        duration_seconds=1.5,
        size_bytes=4,
        checksum="",
        provider="test",
        voice="ef_dora",
    )


@pytest.mark.asyncio
async def test_the_store_round_trips_the_bytes(tmp_path: Path) -> None:
    """Storing writes the file and retrieve returns exactly those bytes."""
    storage = LocalAudioStorage(base_path=str(tmp_path))
    metadata = _metadata()

    stored_path = await storage.store(b"RIFFdata", metadata)

    assert Path(stored_path) == tmp_path / "report-1.wav"
    assert await storage.retrieve(stored_path) == b"RIFFdata"
    assert metadata.checksum != ""


@pytest.mark.asyncio
async def test_the_store_deletes_an_asset(tmp_path: Path) -> None:
    """Deleting removes the file and reports it."""
    storage = LocalAudioStorage(base_path=str(tmp_path))
    stored_path = await storage.store(b"RIFFdata", _metadata())

    assert await storage.delete(stored_path) is True
    assert not Path(stored_path).exists()
    assert await storage.delete(stored_path) is True
