"""add feed folders

Revision ID: b7c1e4a9d2f3
Revises: 435254b79450
Create Date: 2026-10-19 18:50:00.000000

The reader holds one category per feed, so the extra folders of an OPML export
are kept in NAF-owned storage instead of being dropped with the report.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1e4a9d2f3"
down_revision: str | Sequence[str] | None = "435254b79450"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "feed_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_url", sa.String(length=500), nullable=False),
        sa.Column("folder", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_url", "folder", name="uq_feed_folders_feed_url_folder"),
    )
    op.create_index(op.f("ix_feed_folders_id"), "feed_folders", ["id"], unique=False)
    op.create_index(op.f("ix_feed_folders_feed_url"), "feed_folders", ["feed_url"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_feed_folders_feed_url"), table_name="feed_folders")
    op.drop_index(op.f("ix_feed_folders_id"), table_name="feed_folders")
    op.drop_table("feed_folders")
