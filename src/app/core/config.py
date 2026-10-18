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

    # Application
    app_name: str = "naf"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = Field(default="/api/v1")

    # Complement database
    database_url: str = Field(description="PostgreSQL DSN for the NAF database")

    # Miniflux reader API
    miniflux_url: str = Field(description="Base URL of the Miniflux instance")
    miniflux_api_key: str = Field(description="Miniflux API token")
    miniflux_timeout: float = Field(default=30.0)
    miniflux_max_retries: int = Field(default=3)

    # LLM adapter
    llm_provider: str = Field(default="openai")
    llm_api_key: str = Field(default="", description="LLM provider API key")
    llm_model: str = Field(default="")

    # TTS adapter
    tts_provider: str = Field(default="podcastfy")
    tts_voice: str = Field(default="")
    tts_language: str = Field(default="es-ES")
    tts_speed: float = Field(default=1.0)

    # Audio storage
    audio_storage_path: str = Field(default="./storage/audio")
    audio_base_url: str = Field(default="")


def load_settings() -> Settings:
    """Instantiate settings once at startup so failures surface early."""
    return Settings()  # type: ignore[call-arg]


settings = load_settings()
