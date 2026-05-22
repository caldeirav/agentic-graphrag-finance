"""Pydantic models for console trace events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TraceLevel(StrEnum):
    QUIET = "quiet"
    NORMAL = "normal"
    VERBOSE = "verbose"


class TraceEventType(StrEnum):
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    LLM_IO = "llm_io"
    ROUTING_DECISION = "routing_decision"
    EVIDENCE_SNAPSHOT = "evidence_snapshot"


class LlmIoRecord(BaseModel):
    model_id: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    messages_preview: list[dict[str, str]] = Field(default_factory=list)
    response_preview: str = ""
    latency_ms: int = 0
    error: str | None = None


class TraceEvent(BaseModel):
    stage_id: str
    event_type: TraceEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int | None = None
    decision_summary: str = ""
    payload: dict = Field(default_factory=dict)
    llm_io: LlmIoRecord | None = None


class TraceRunConfig(BaseModel):
    level: TraceLevel = TraceLevel.NORMAL
    emit_jsonl: bool = False
    prompt_preview_chars: int = 800
    excerpt_preview_chars: int = 400
    use_color: bool = True
    panel_enabled: bool = True

    @property
    def show_human(self) -> bool:
        return self.level != TraceLevel.QUIET

    @property
    def verbose(self) -> bool:
        return self.level == TraceLevel.VERBOSE
