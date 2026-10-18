class NafException(Exception):
    """Base exception for NAF."""

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(self.message)


class MinifluxAPIError(NafException):
    """Error communicating with Miniflux API."""

    pass


class ClassificationError(NafException):
    """Error during classification."""

    pass


class ReportGenerationError(NafException):
    """Error during report generation."""

    pass


class TTSError(NafException):
    """Error during TTS generation."""

    pass


class CitationValidationError(NafException):
    """Citation validation failed."""

    pass
