"""add story official and uncertainties

Revision ID: f1a2b3c4d5e6
Revises: e3b8c4d92a17
Create Date: 2026-11-24 18:40:00.000000

A story records whether the item is the creator's own announcement and which
statements the entries do not support. Both fields are advisory: they never
replace the citations that support a claim.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e3b8c4d92a17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("digest_stories", sa.Column("official", sa.Boolean(), nullable=True))
    op.add_column("digest_stories", sa.Column("uncertainties", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("digest_stories", "uncertainties")
    op.drop_column("digest_stories", "official")
