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

    sec_api_key: str = Field(default="", alias="SEC_API_KEY")
    sec_api_requests_per_second: float = Field(default=2.0, alias="SEC_API_REQUESTS_PER_SECOND")
    sec_downloads_root: Path = Field(
        default=Path("data/raw/sec_downloads"),
        alias="SEC_DOWNLOADS_ROOT",
    )
    ticker_map_cache: Path = Field(default=Path("data/cache/sec-api/ticker_map.json"))


@lru_cache
def get_settings() -> IngestionSettings:
    return IngestionSettings()


def require_sec_api_key() -> str:
    key = get_settings().sec_api_key or os.environ.get("SEC_API_KEY", "")
    if not key or not key.strip():
        raise ConfigurationError(
            "SEC_API_KEY is not set. Add it to .env (see .env.example). "
            "Obtain a key at https://sec-api.io"
        )
    return key.strip()


def is_mock_mode() -> bool:
    key = require_sec_api_key()
    return key in ("test-mock", "mock", "test")
