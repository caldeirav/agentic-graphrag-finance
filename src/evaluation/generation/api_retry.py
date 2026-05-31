"""Transient retry helper for live generation/eval HTTP clients."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def with_transient_retry[T](
    func: Callable[[], T],
    *,
    max_attempts: int = 5,
    label: str = "API",
) -> T:
    """Retry on rate limits, server errors, and transport disconnects."""
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
                "%s HTTP retry %s/%s (status %s): %s",
                label,
                attempt + 1,
                max_attempts,
                exc.response.status_code,
                exc,
            )
        except httpx.RequestError as exc:
            last_exc = exc
            logger.warning(
                "%s transport retry %s/%s: %s",
                label,
                attempt + 1,
                max_attempts,
                exc,
            )
        if attempt + 1 < max_attempts:
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise last_exc  # type: ignore[misc]
