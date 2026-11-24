"""add report provenance

Revision ID: c5e2a7f19b04
Revises: b7c1e4a9d2f3
Create Date: 2026-11-24 10:00:00.000000

A report must stay reproducible after the entries leave the reader page it was
built from. The included entry identifiers, the generator metadata, and the
failure reason are kept beside the existing filter, cursor, and version columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e2a7f19b04"
down_revision: str | Sequence[str] | None = "b7c1e4a9d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("digests", sa.Column("entry_ids", sa.JSON(), nullable=True))
    op.add_column("digests", sa.Column("meta", sa.JSON(), nullable=True))
    op.add_column("digests", sa.Column("error_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("digests", "error_summary")
    op.drop_column("digests", "meta")
    op.drop_column("digests", "entry_ids")
