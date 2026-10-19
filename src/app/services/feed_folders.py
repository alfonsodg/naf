"""Keep the folders a feed was found under, besides the one applied.

The reader holds one category per feed, so the extra folders of an OPML export
are NAF-owned data: they are the only trace of the tags the user had.
"""

from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FeedFolder


class FolderRecorder(Protocol):
    """Keep the folders found for a feed."""

    def record(self, feed_url: str, folders: list[str]) -> None:
        """Store the folders found for a feed, replacing the previous ones."""


class FeedFolderStore:
    """Store and read the folders reported by an intake."""

    def __init__(self, session: Session) -> None:
        """Bind the store to a database session."""
        self.session = session

    def record(self, feed_url: str, folders: list[str]) -> None:
        """Store the folders found for a feed, replacing the previous ones."""
        self.session.execute(delete(FeedFolder).where(FeedFolder.feed_url == feed_url))
        for folder in folders:
            self.session.add(FeedFolder(feed_url=feed_url, folder=folder))
        self.session.commit()

    def list_folders(self) -> list[dict[str, Any]]:
        """Return every stored folder with the feed it belongs to."""
        rows = self.session.execute(select(FeedFolder).order_by(FeedFolder.feed_url, FeedFolder.folder)).scalars()
        return [{"feed_url": row.feed_url, "folder": row.folder} for row in rows]
