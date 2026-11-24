"""NAF-owned record of the folders a feed was found under."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.db.base import Base


def _now() -> datetime:
    """Return the current UTC time in the naive form the columns use."""
    return datetime.now(UTC).replace(tzinfo=None)


class FeedFolder(Base):
    """A folder found in a source document for a feed, besides the applied one.

    The reader holds one category per feed, so the extra folders of an OPML
    export are kept here instead of being dropped with the report.
    """

    __tablename__ = "feed_folders"
    __table_args__ = (UniqueConstraint("feed_url", "folder", name="uq_feed_folders_feed_url_folder"),)

    id = Column(Integer, primary_key=True, index=True)
    feed_url = Column(String(500), nullable=False, index=True)
    folder = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_now)
