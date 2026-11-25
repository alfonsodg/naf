"""Report generator and selection settings."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
    }
    base.update(overrides)
    return Settings(**base)


def test_the_generator_has_a_bounded_default_configuration() -> None:
    """Every report setting has a value that bounds one request."""
    settings = _settings()

    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == ""
    assert settings.llm_timeout == 120.0
    assert settings.llm_max_output_tokens == 6000
    assert settings.report_max_entries == 40
    assert settings.report_default_days == 7
    assert settings.edition_retention_days == 90
    assert settings.edition_cleanup_enabled is True


def test_the_generator_reads_the_provider_settings_from_the_environment(monkeypatch) -> None:
    """A deployment points the adapter at its provider without code changes."""
    monkeypatch.setenv("NAF_LLM_BASE_URL", "https://provider.test/v1")
    monkeypatch.setenv("NAF_LLM_MODEL", "report-model")
    monkeypatch.setenv("NAF_LLM_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("NAF_REPORT_MAX_ENTRIES", "40")

    settings = _settings()

    assert settings.llm_base_url == "https://provider.test/v1"
    assert settings.llm_model == "report-model"
    assert settings.llm_max_output_tokens == 1200
    assert settings.report_max_entries == 40


def test_the_speech_engine_has_a_documented_default_configuration() -> None:
    """The audio routes start disabled until a model and voices file are configured."""
    settings = _settings()

    assert settings.tts_model_path == ""
    assert settings.tts_voices_path == ""
    assert settings.tts_voice == "ef_dora"
    assert settings.tts_language == "es-ES"
    assert settings.tts_speed == 1.0
    assert settings.tts_segment_retries == 2
    assert settings.tts_segment_retry_delay == 0.5


def test_the_segment_retries_and_delay_are_bounded(monkeypatch) -> None:
    """A deployment can retry a segment more or wait less, never without a bound."""
    monkeypatch.setenv("NAF_TTS_SEGMENT_RETRIES", "4")
    monkeypatch.setenv("NAF_TTS_SEGMENT_RETRY_DELAY", "0.25")

    settings = _settings()

    assert settings.tts_segment_retries == 4
    assert settings.tts_segment_retry_delay == 0.25

    monkeypatch.setenv("NAF_TTS_SEGMENT_RETRIES", "6")
    with pytest.raises(ValidationError):
        _settings()

    monkeypatch.setenv("NAF_TTS_SEGMENT_RETRIES", "2")
    monkeypatch.setenv("NAF_TTS_SEGMENT_RETRY_DELAY", "0")
    with pytest.raises(ValidationError):
        _settings()


def test_the_speech_speed_is_bounded(monkeypatch) -> None:
    """A deployment can speed the voice up but never outside the documented range."""
    monkeypatch.setenv("NAF_TTS_SPEED", "1.5")

    assert _settings().tts_speed == 1.5

    monkeypatch.setenv("NAF_TTS_SPEED", "3.0")
    with pytest.raises(ValidationError):
        _settings()
