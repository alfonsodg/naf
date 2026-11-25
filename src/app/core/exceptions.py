"""Domain exceptions. Every error carries a stable identifier."""


class NafError(Exception):
    """Base error for NAF domain failures."""

    def __init__(self, message: str = "") -> None:
        """Store the human-readable message."""
        self.message = message
        super().__init__(self.message)


class MinifluxAPIError(NafError):
    """Error communicating with the Miniflux API."""

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        """Store the message and the HTTP status that caused it."""
        super().__init__(message)
        self.status_code = status_code


class ClassificationError(NafError):
    """Error during classification."""


class ReportGenerationError(NafError):
    """Error during report generation."""


class TTSError(NafError):
    """Error during speech synthesis."""


class CitationValidationError(NafError):
    """A factual claim lacks a valid citation."""
