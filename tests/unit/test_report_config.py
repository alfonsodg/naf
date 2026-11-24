"""Report generator and selection settings."""

from typing import Any

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
    assert settings.llm_timeout > 0
    assert 256 <= settings.llm_max_output_tokens <= 32000
    assert 1 <= settings.report_max_entries <= 500
    assert 1 <= settings.report_default_days <= 90


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
