"""
Centralized configuration for SEO Agent Pro backend.
Uses Pydantic Settings to load from environment variables and .env file.
"""

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── API Keys ──
    openai_api_key: str = ""
    tavily_api_key: str = ""
    serper_api_key: str = ""
    pagespeed_api_key: str = ""

    # ── LLM Configuration ──
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # ── CORS ──
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Scraper ──
    scraper_timeout: int = 15
    scraper_max_retries: int = 3
    playwright_timeout: int = 40000

    # ── Rate Limiting ──
    rate_limit_per_minute: int = 30

    # ── Cache ──
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 200

    # ── RAG / Vector Store ──
    embedding_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = "./chroma_data"
    rag_knowledge_results: int = 4
    rag_scan_results: int = 5
    chat_max_history: int = 20

    # ── Application ──
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
