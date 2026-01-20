"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_path: str = "./data/canopy.db"

    # LLM API Keys
    perplexity_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM Provider selection
    llm_provider: Literal["perplexity", "claude"] = "perplexity"

    # Scraping configuration
    scrape_delay_seconds: float = 2.0

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
