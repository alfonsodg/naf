"""Remove report editions and their audio once the retention window closes.

Decision 8 keeps editions immutable while they are inside the window and makes
their cleanup configurable. This service never touches reader data, ingestion
runs, or anything younger than the cutoff, and the route defaults to a dry run.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ports.storage import AudioStorage
from app.models import AudioAsset, Digest


class MaintenanceService:
    """Preview and apply the cleanup of old editions."""

    def __init__(self, session: Session, storage: AudioStorage, settings: Settings) -> None:
        """Store the session, the audio backend, and the configured limits."""
        self.session = session
        self.storage = storage
        self.settings = settings

    def _cutoff(self, days: int) -> datetime:
        """Return the oldest instant an edition may keep."""
        return datetime.now(UTC) - timedelta(days=days)

    def _old_editions(self, cutoff: datetime) -> list[Digest]:
        """Return the editions created before the cutoff, oldest first."""
        statement = select(Digest).where(Digest.created_at < cutoff).order_by(Digest.created_at.asc())
        return list(self.session.execute(statement).scalars().all())

    def _assets(self, digest: Digest) -> list[AudioAsset]:
        """Return the audio assets of one edition."""
        statement = select(AudioAsset).where(AudioAsset.digest_id == digest.id)
        return list(self.session.execute(statement).scalars().all())

    def preview(self, days: int) -> dict[str, Any]:
        """Describe what a cleanup with this window would remove."""
        cutoff = self._cutoff(days)
        editions = self._old_editions(cutoff)
        assets = [asset for digest in editions for asset in self._assets(digest)]
        return {
            "days": days,
            "cutoff": cutoff.isoformat(),
            "editions": [digest.id for digest in editions],
            "audio_assets": [asset.id for asset in assets],
            "bytes": sum(_size(asset) for asset in assets),
            "filenames": [asset.filename for asset in assets],
        }

    async def clean(self, days: int, dry_run: bool = True) -> dict[str, Any]:
        """Delete the editions older than the window, or only describe them."""
        report = self.preview(days)
        if dry_run:
            report["dry_run"] = True
            report["deleted_editions"] = 0
            report["deleted_assets"] = 0
            report["deleted_bytes"] = 0
            report["missing_files"] = 0
            return report

        deleted_bytes = 0
        missing = 0
        removed_files = 0
        for asset in [asset for digest in self._old_editions(self._cutoff(days)) for asset in self._assets(digest)]:
            if await self.storage.delete(asset.file_path):
                removed_files += 1
                deleted_bytes += _size(asset)
            else:
                missing += 1
            self.session.delete(asset)

        editions = self._old_editions(self._cutoff(days))
        for digest in editions:
            self.session.delete(digest)
        self.session.commit()
        report.update(
            {
                "dry_run": False,
                "deleted_editions": len(editions),
                "deleted_assets": removed_files + missing,
                "deleted_bytes": deleted_bytes,
                "missing_files": missing,
            }
        )
        return report


def _size(asset: AudioAsset) -> int:
    """Return the recorded size of an asset, or zero when it was never stored."""
    return int(asset.size_bytes or 0)
