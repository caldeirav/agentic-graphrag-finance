"""Trace configuration loader and CLI level resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from tracing.console_trace.models import TraceLevel, TraceRunConfig


def load_trace_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/trace.yaml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def resolve_trace_level(
    cli_trace: str | None = None,
    *,
    env_trace: str | None = None,
) -> TraceLevel:
    if cli_trace:
        return TraceLevel(cli_trace.strip().lower())
    raw = env_trace or os.environ.get("AGENT_QUERY_TRACE", "").strip()
    if raw:
        return TraceLevel(raw.lower())
    if sys.stderr.isatty():
        return TraceLevel.NORMAL
    return TraceLevel.QUIET


def build_trace_run_config(
    level: TraceLevel,
    *,
    emit_jsonl: bool = False,
) -> TraceRunConfig:
    cfg = load_trace_config()
    use_color = (
        sys.stderr.isatty()
        and os.environ.get("NO_COLOR", "") == ""
        and level != TraceLevel.QUIET
    )
    return TraceRunConfig(
        level=level,
        emit_jsonl=emit_jsonl,
        prompt_preview_chars=int(
            os.environ.get("TRACE_PROMPT_PREVIEW_CHARS", cfg.get("prompt_preview_chars", 800))
        ),
        excerpt_preview_chars=int(
            os.environ.get("TRACE_EXCERPT_PREVIEW_CHARS", cfg.get("excerpt_preview_chars", 400))
        ),
        use_color=use_color,
        panel_enabled=bool(cfg.get("panel_enabled", True)),
    )
