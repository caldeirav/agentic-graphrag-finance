"""Ingestion layer configuration from environment."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Missing or invalid ingestion configuration."""


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sec_edgar_user_agent: str = Field(default="", alias="SEC_EDGAR_USER_AGENT")
    edgar_requests_per_second: float = Field(default=8.0, alias="EDGAR_REQUESTS_PER_SECOND")
    sec_downloads_root: Path = Field(
        default=Path("data/raw/sec_downloads"),
        alias="SEC_DOWNLOADS_ROOT",
    )
    ticker_map_cache: Path = Field(default=Path("data/cache/edgar/ticker_map.json"))
    fixture_downloads_root: Path = Field(
        default=Path("tests/fixtures/sec_downloads"),
        alias="FIXTURE_DOWNLOADS_ROOT",
    )


@lru_cache
def get_settings() -> IngestionSettings:
    return IngestionSettings()


def require_edgar_user_agent() -> str:
    ua = get_settings().sec_edgar_user_agent or os.environ.get("SEC_EDGAR_USER_AGENT", "")
    if not ua or not ua.strip():
        raise ConfigurationError(
            "SEC_EDGAR_USER_AGENT is not set. Add your name and email to .env "
            "(SEC fair-access policy). See .env.example."
        )
    return ua.strip()


def is_fixture_ingestion() -> bool:
    """Use bundled XBRL packages under tests/fixtures (CI and offline dev)."""
    return os.environ.get("USE_FIXTURE_INGESTION", "0") == "1"
