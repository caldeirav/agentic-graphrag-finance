"""Emit trace events into LangGraph state."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from tracing.console_trace.models import LlmIoRecord, TraceEvent, TraceEventType


def trace_events_patch(events: list[TraceEvent]) -> dict:
    return {"trace_events": events}


def trace_stage_start(stage_id: str) -> dict:
    event = TraceEvent(
        stage_id=stage_id,
        event_type=TraceEventType.STAGE_START,
        timestamp=datetime.now(UTC),
    )
    return trace_events_patch([event])


def trace_stage_end(
    stage_id: str,
    *,
    duration_ms: int,
    decision_summary: str,
    payload: dict | None = None,
) -> dict:
    event = TraceEvent(
        stage_id=stage_id,
        event_type=TraceEventType.STAGE_END,
        timestamp=datetime.now(UTC),
        duration_ms=duration_ms,
        decision_summary=decision_summary,
        payload=payload or {},
    )
    return trace_events_patch([event])


def trace_llm_io(
    stage_id: str,
    *,
    record: LlmIoRecord,
    duration_ms: int,
) -> dict:
    event = TraceEvent(
        stage_id=stage_id,
        event_type=TraceEventType.LLM_IO,
        timestamp=datetime.now(UTC),
        duration_ms=duration_ms,
        llm_io=record,
        decision_summary=f"LLM {record.model_id or 'local'} ({duration_ms} ms)",
    )
    return trace_events_patch([event])


class StageTimer:
    def __init__(self, stage_id: str) -> None:
        self.stage_id = stage_id
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
