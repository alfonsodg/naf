"""Test configuration: deterministic environment values for the test suite.

Per GENERAL.md, deterministic literals are allowed in test-only fixtures.
These values are never used outside tests and contain no real credentials.
"""

import os

os.environ.setdefault("NAF_DATABASE_URL", "postgresql://test:test@localhost:5432/naf_test")
os.environ.setdefault("NAF_MINIFLUX_URL", "http://localhost:8080")
os.environ.setdefault("NAF_MINIFLUX_API_KEY", "test-token")
