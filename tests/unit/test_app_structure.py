"""Contract and structure checks for the application package."""

from app.core.ports import Classifier, FeedReader, ReportGenerator, TTSProvider


def test_app_imports() -> None:
    """The FastAPI application loads with the configured identity."""
    from app.main import app

    assert app.title == "naf"


def test_config_loads() -> None:
    """Settings expose the documented identity values."""
    from app.core.config import settings

    assert settings.app_name == "naf"
    assert settings.app_version == "0.1.0"


def test_ports_importable() -> None:
    """Every port is importable from the single composition module."""
    assert FeedReader is not None
    assert Classifier is not None
    assert ReportGenerator is not None
    assert TTSProvider is not None


def test_models_importable() -> None:
    """NAF-owned ORM models load from one place."""
    from app.models import AudioAsset, Digest, DigestStory

    assert Digest is not None
    assert DigestStory is not None
    assert AudioAsset is not None


def test_layering_has_no_backwards_imports() -> None:
    """Ports and schemas must not import adapters, routers, or services."""
    forbidden = ("app.adapters", "app.routers", "app.services", "app.db")

    for module in ("app.core.ports", "app.schemas"):
        namespace = __import__(module, fromlist=["__file__"])
        source = open(namespace.__file__, encoding="utf-8").read()  # noqa: SIM115
        for target in forbidden:
            assert f"import {target}" not in source


def test_helpers_without_a_consumer_stay_removed() -> None:
    """A public helper without a caller is not reintroduced."""
    from app.core import feed_urls
    from app.core.ports import feed_reader
    from app.services import collector

    assert not hasattr(feed_urls, "is_feed_document")
    assert not hasattr(feed_reader.FeedReader, "mark_entry_read")
    assert not hasattr(collector.Collector, "get_entries")
