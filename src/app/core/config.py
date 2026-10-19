"""Typed application settings. Configurable values fail fast when absent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables (NAF_ prefix).

    No defaults are declared for deployment-specific or integration values:
    a missing variable raises at import time instead of silently falling back.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="NAF_",
        extra="ignore",
    )

    # Application identity (not deployment configuration)
    app_name: str = "naf"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Complement database
    database_url: str = Field(description="PostgreSQL DSN for the NAF database")

    # Miniflux reader API
    miniflux_url: str = Field(description="Base URL of the Miniflux instance")
    miniflux_api_key: str = Field(description="Miniflux API token")
    miniflux_timeout: float = 30.0
    miniflux_max_retries: int = 3

    # Feed intake and validation
    feed_validation_timeout: float = Field(
        default=15.0,
        gt=0,
        description="Per-feed HTTP timeout when validating a candidate feed",
    )
    feed_validation_concurrency: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Maximum parallel feed probes during one intake",
    )
    feed_validation_max_redirects: int = Field(
        default=5,
        ge=0,
        le=10,
        description="Redirect hops followed while validating a feed",
    )
    feed_validation_per_host_concurrency: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Maximum parallel probes against the same host",
    )
    feed_validation_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Retries after a host asks the client to wait",
    )
    feed_validation_retry_backoff: float = Field(
        default=1.0,
        gt=0,
        description="Base delay in seconds between retries of a refused request",
    )
    feed_intake_max_bytes: int = Field(
        default=1_000_000,
        gt=0,
        description="Largest accepted intake payload or feed response body",
    )
    feed_intake_max_batch: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum candidates probed in one intake request",
    )
    feed_intake_time_budget: float = Field(
        default=25.0,
        gt=0,
        description="Seconds one intake request may spend probing candidates",
    )

    # LLM adapter
    llm_provider: str = "openai"
    llm_api_key: str = Field(default="", description="LLM provider API key")
    llm_model: str = ""

    # TTS adapter
    tts_provider: str = "podcastfy"
    tts_voice: str = ""
    tts_language: str = "es-ES"
    tts_speed: float = 1.0

    # Audio storage
    audio_storage_path: str = "./storage/audio"
    audio_base_url: str = ""

    @property
    def is_development(self) -> bool:
        """Report whether the service runs with development conveniences."""
        return self.debug


def load_settings() -> Settings:
    """Instantiate settings once so missing values surface at import time."""
    return Settings()  # type: ignore[call-arg]


settings = load_settings()
