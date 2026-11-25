"""add entry classification and model mentions

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-24 18:55:00.000000

NAF owns the reading of an entry: the suggested categories and tags, whether the
user corrected them, and the models the entry names with their evidence. The
reader keeps the entry itself, so these tables reference it by number only.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "entry_classifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("pub_type", sa.String(length=100), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Boolean(), nullable=True),
        sa.Column("review_needed", sa.Boolean(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entry_classifications_id"), "entry_classifications", ["id"], unique=False)
    op.create_index(op.f("ix_entry_classifications_entry_id"), "entry_classifications", ["entry_id"], unique=True)

    op.create_table(
        "entry_model_mentions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("creator", sa.String(length=255), nullable=True),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entry_model_mentions_id"), "entry_model_mentions", ["id"], unique=False)
    op.create_index(op.f("ix_entry_model_mentions_entry_id"), "entry_model_mentions", ["entry_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_entry_model_mentions_entry_id"), table_name="entry_model_mentions")
    op.drop_index(op.f("ix_entry_model_mentions_id"), table_name="entry_model_mentions")
    op.drop_table("entry_model_mentions")
    op.drop_index(op.f("ix_entry_classifications_entry_id"), table_name="entry_classifications")
    op.drop_index(op.f("ix_entry_classifications_id"), table_name="entry_classifications")
    op.drop_table("entry_classifications")
