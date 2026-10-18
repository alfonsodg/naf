from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "naf"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database (complement DB)
    database_url: str = "postgresql://user:password@localhost:5432/naf"

    # Miniflux API
    miniflux_url: str = "http://localhost:8080"
    miniflux_api_key: Optional[str] = None
    miniflux_timeout: float = 30.0
    miniflux_max_retries: int = 3

    # LLM
    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"

    # TTS
    tts_provider: str = "podcastfy"
    tts_voice: Optional[str] = None
    tts_language: str = "es-ES"
    tts_speed: float = 1.0

    # Audio storage
    audio_storage_path: str = "./storage/audio"
    audio_base_url: Optional[str] = None

    # Security / SSRF (basic)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]


settings = Settings()
