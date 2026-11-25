"""API error envelope per the documented REST conventions."""

from typing import Any


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build the standard error payload."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }
