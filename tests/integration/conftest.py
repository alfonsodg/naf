"""Integration suite configuration.

Integration tests require the persistent services of the designated remote test
server recorded in `REMOTE.md`. They never run on the local workstation: no
database or cache is installed locally. When the remote endpoint is not
configured these tests are skipped instead of silently passing, and unit tests
are unaffected.
"""

import os
from pathlib import Path

import pytest

REMOTE_BASE_URL = "NAF_TEST_BASE_URL"
INTEGRATION_DIR = str(Path(__file__).resolve().parent)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration items only, and only when the remote endpoint is absent."""
    if os.environ.get(REMOTE_BASE_URL):
        return

    skip = pytest.mark.skip(reason=f"{REMOTE_BASE_URL} is not set: run integration tests on the remote test server")
    for item in items:
        if str(item.path).startswith(INTEGRATION_DIR):
            item.add_marker(skip)
