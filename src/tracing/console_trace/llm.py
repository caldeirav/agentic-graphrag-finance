"""Traced LLM invocation for ask-graph stages."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import BaseMessage

from tracing.console_trace.config import load_trace_config
from tracing.console_trace.context import get_trace_reporter
from tracing.console_trace.emitter import trace_llm_io
from tracing.console_trace.models import LlmIoRecord


def _preview_messages(messages: list[BaseMessage], limit: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in messages:
        role = getattr(msg, "type", None) or msg.__class__.__name__.replace("Message", "").lower()
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if len(content) > limit:
            content = content[: limit - 3] + "..."
        out.append({"role": str(role), "content": content})
    return out


def _preview_response(content: object, limit: int) -> str:
    text = content if isinstance(content, str) else str(content)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def traced_llm_invoke(
    stage_id: str,
    llm: Any,
    messages: list[BaseMessage],
) -> tuple[Any, dict]:
    """Invoke LLM; return (response, state patch with trace_events)."""
    cfg = load_trace_config()
    limit = int(cfg.get("prompt_preview_chars", 800))
    reporter = get_trace_reporter()
    if reporter and reporter.config.verbose:
        limit = max(limit, reporter.config.prompt_preview_chars)

    started = time.perf_counter()
    error: str | None = None
    resp = None
    try:
        resp = llm.invoke(messages)
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        latency = int((time.perf_counter() - started) * 1000)
        model_id = (
            getattr(llm, "model_name", None) or getattr(llm, "model", None) or "local-llm"
        )
        response_preview = ""
        if resp is not None:
            response_preview = _preview_response(
                getattr(resp, "content", resp),
                limit,
            )
        record = LlmIoRecord(
            model_id=str(model_id),
            temperature=getattr(llm, "temperature", None),
            max_tokens=getattr(llm, "max_tokens", None),
            messages_preview=_preview_messages(messages, limit),
            response_preview=response_preview,
            latency_ms=latency,
            error=error,
        )
        patch = trace_llm_io(stage_id, record=record, duration_ms=latency)

    return resp, patch
