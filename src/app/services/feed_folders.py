"""Keep the folders a feed was found under, besides the one applied.

The reader holds one category per feed, so the extra folders of an OPML export
are NAF-owned data: they are the only trace of the tags the user had.
"""

from typing import Any, Protocol, cast

from sqlalchemy import delete, func, select
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

    def folders(self) -> list[str]:
        """Return the distinct folder names, sorted.

        A folder is one name the intake found in the source document, however
        many feeds sit under it. This is what a caller uses to discover the
        available filters; ``feed_urls`` then opens one of them.
        """
        rows = cast(
            "list[str]",
            list(self.session.execute(select(FeedFolder.folder).distinct().order_by(FeedFolder.folder)).scalars()),
        )
        return rows

    def feed_urls(self, folder: str) -> list[str]:
        """Return the feed URLs stored under one folder, sorted.

        The URL is the key the intake recorded; the reader identifies the same
        subscription by an integer, so a caller maps this list through the
        reader's feed list before selecting entries.
        """
        rows = cast(
            "list[str]",
            list(
                self.session.execute(
                    select(FeedFolder.feed_url).where(FeedFolder.folder == folder).order_by(FeedFolder.feed_url)
                ).scalars()
            ),
        )
        return rows

    def folder_counts(self) -> list[dict[str, Any]]:
        """Return each distinct folder with the number of feeds stored under it."""
        rows = cast(
            "list[tuple[str, int]]",
            self.session.execute(
                select(FeedFolder.folder, func.count(FeedFolder.feed_url))
                .group_by(FeedFolder.folder)
                .order_by(FeedFolder.folder)
            ).all(),
        )
        return [{"folder": folder, "feed_count": int(count)} for folder, count in rows]
