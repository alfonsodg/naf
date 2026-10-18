def test_app_imports():
    from app.main import app

    assert app.title == "naf"


def test_config_loads():
    from app.core.config import settings

    assert settings.app_name == "naf"
    assert settings.app_version == "0.1.0"


def test_contracts_importable():
    from app.contracts import FeedReader, Classifier, ReportGenerator

    assert FeedReader is not None
    assert Classifier is not None
    assert ReportGenerator is not None


def test_models_importable():
    from app.models import Digest, DigestStory, AudioAsset

    assert Digest is not None
    assert DigestStory is not None
    assert AudioAsset is not None
