"""Deferred judging configuration for reproduction (013)."""

from __future__ import annotations

import os
from typing import Literal

from models.reproduction import DeferJudgeConfig

_FINAL_JUDGE_STATUSES = frozenset({"ok", "degraded", "not_evaluable"})


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes"}


def resolve_defer_config(*, cli_defer: bool | None = None) -> DeferJudgeConfig:
    enabled = _env_truthy("REPRO_DEFER_JUDGE") if cli_defer is None else cli_defer
    judge_after_raw = os.environ.get("REPRO_JUDGE_AFTER", "each_variant").strip().lower()
    judge_after: Literal["each_variant", "all_variants"] = (
        "all_variants" if judge_after_raw == "all_variants" else "each_variant"
    )
    concurrency_raw = os.environ.get("REPRO_JUDGE_CONCURRENCY", "2").strip()
    try:
        concurrency = max(1, int(concurrency_raw))
    except ValueError:
        concurrency = 2
    return DeferJudgeConfig(
        enabled=enabled,
        judge_after=judge_after,
        concurrency=concurrency,
        allow_pending_export=_env_truthy("REPRO_ALLOW_PENDING_EXPORT"),
    )


def should_skip_post_query_audit(metadata: dict[str, str]) -> bool:
    """True when repro defer is active and request is a benchmark item."""
    if not _env_truthy("REPRO_DEFER_JUDGE") and metadata.get("defer_judge", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return False
    return bool(metadata.get("benchmark_item"))


def is_final_judge_status(status: str | None) -> bool:
    return (status or "").lower() in _FINAL_JUDGE_STATUSES
