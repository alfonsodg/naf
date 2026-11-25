"""Ports (interfaces) enabling dependency inversion.

Adapters implement these; services depend only on them.
"""

from app.core.ports.classifier import Classifier
from app.core.ports.feed_reader import FeedReader
from app.core.ports.feed_validator import FeedProbe, FeedValidator, FeedVerdict
from app.core.ports.report_generator import ReportGenerator
from app.core.ports.storage import AudioStorage
from app.core.ports.tts import TTSProvider

__all__ = [
    "AudioStorage",
    "Classifier",
    "FeedProbe",
    "FeedReader",
    "FeedValidator",
    "FeedVerdict",
    "ReportGenerator",
    "TTSProvider",
]
