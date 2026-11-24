"""The migration chain is linear and every revision is reversible."""

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script() -> ScriptDirectory:
    """Load the migration scripts from the repository configuration."""
    return ScriptDirectory.from_config(Config("alembic.ini"))


def test_the_chain_has_exactly_one_head() -> None:
    """Two heads would make the deployed schema ambiguous."""
    assert _script().get_heads() == ["f1a2b3c4d5e6"]


def test_every_revision_defines_upgrade_and_downgrade() -> None:
    """A migration without a downgrade cannot be rolled back."""
    for revision in _script().walk_revisions():
        assert callable(revision.module.upgrade)
        assert callable(revision.module.downgrade)
