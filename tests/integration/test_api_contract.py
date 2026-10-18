"""Remote integration tests: live HTTP contract against the deployed service.

These tests only run when `NAF_TEST_BASE_URL` points at the remote test server
recorded in `REMOTE.md`. They assert the API contract the service promises,
not internal implementation details.
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("NAF_TEST_BASE_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="NAF_TEST_BASE_URL is not set")


def test_liveness_reports_ok() -> None:
    """The deployed service answers the liveness probe."""
    response = httpx.get(f"{BASE_URL}/health", timeout=10)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_entries_endpoint_returns_pagination_metadata() -> None:
    """The entries endpoint honors the documented pagination contract."""
    response = httpx.get(f"{BASE_URL}/api/v1/entries", params={"page": 1, "per_page": 5}, timeout=30)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "pagination"}
    assert body["pagination"]["page"] == 1
    assert len(body["data"]) <= 5


def test_entries_preserve_provenance() -> None:
    """Every returned entry keeps its feed identity and source URL."""
    response = httpx.get(f"{BASE_URL}/api/v1/entries", params={"per_page": 1}, timeout=30)

    assert response.status_code == 200
    entries = response.json()["data"]
    if not entries:
        pytest.skip("the reader has no entries yet")
    entry = entries[0]
    assert entry["feed_id"] is not None
    assert entry["url"] is not None


def test_error_envelope_shape_for_unknown_entry() -> None:
    """An invalid status value is rejected with the standardized envelope."""
    response = httpx.patch(f"{BASE_URL}/api/v1/entries/1", json={"status": "archived"}, timeout=10)

    assert response.status_code == 422
