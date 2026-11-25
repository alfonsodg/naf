"""add entry relations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-25 01:50:00.000000

A report groups coverage of the same event; the pair is stored so the relation
survives the text. No entry is deleted by a relation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "entry_relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("related_entry_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "related_entry_id", "report_id", name="uq_entry_relations_pair_report"),
    )
    op.create_index(op.f("ix_entry_relations_id"), "entry_relations", ["id"], unique=False)
    op.create_index(op.f("ix_entry_relations_entry_id"), "entry_relations", ["entry_id"], unique=False)
    op.create_index(op.f("ix_entry_relations_related_entry_id"), "entry_relations", ["related_entry_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_entry_relations_related_entry_id"), table_name="entry_relations")
    op.drop_index(op.f("ix_entry_relations_entry_id"), table_name="entry_relations")
    op.drop_index(op.f("ix_entry_relations_id"), table_name="entry_relations")
    op.drop_table("entry_relations")
