"""Shared SEC EDGAR HTTP retry, throttling, and headers."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

import httpx

from ingestion.settings import get_settings, require_edgar_user_agent

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "agentic-graphrag-finance contact@example.com"

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_last_request = 0.0


def edgar_user_agent() -> str:
    return os.environ.get("SEC_EDGAR_USER_AGENT", DEFAULT_USER_AGENT)


def edgar_headers(*, json_accept: bool = False) -> dict[str, str]:
    require_edgar_user_agent()
    headers = {"User-Agent": edgar_user_agent()}
    if json_accept:
        headers["Accept"] = "application/json"
    return headers


def edgar_throttle() -> None:
    """Respect EDGAR fair-access rate from settings."""
    global _last_request
    settings = get_settings()
    min_interval = 1.0 / max(settings.edgar_requests_per_second, 0.1)
    now = time.time()
    elapsed = now - _last_request
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request = time.time()


def with_edgar_retry[T](func: Callable[[], T], *, max_attempts: int = 5) -> T:
    """Retry EDGAR HTTP calls on rate limits, server errors, and transient transport faults."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code not in _RETRYABLE_STATUS:
                raise
            logger.warning(
                "EDGAR HTTP retry %s/%s (status %s): %s",
                attempt + 1,
                max_attempts,
                exc.response.status_code,
                exc,
            )
        except httpx.RequestError as exc:
            last_exc = exc
            logger.warning(
                "EDGAR transport retry %s/%s: %s",
                attempt + 1,
                max_attempts,
                exc,
            )
        if attempt + 1 < max_attempts:
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise last_exc  # type: ignore[misc]
