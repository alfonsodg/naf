"""add audio segments

Revision ID: e3b8c4d92a17
Revises: c5e2a7f19b04
Create Date: 2026-11-24 11:00:00.000000

A spoken edition keeps the timed transcript of what the voice reads, so the
player can follow the audio and one failed segment can be synthesized again
without regenerating the whole report. The column is a JSON list of segment
records: index, story index, start and end instants, and the spoken text.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b8c4d92a17"
down_revision: str | Sequence[str] | None = "c5e2a7f19b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("audio_assets", sa.Column("segments", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("audio_assets", "segments")
