"""Stream human-readable trace to stderr and optional JSONL."""

from __future__ import annotations

import re
import sys
from collections import defaultdict

from retrieval.orchestration.state import AgentState
from tracing.console_trace.models import TraceEvent, TraceRunConfig
from tracing.console_trace.registry import ASK_TRACE_REGISTRY


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class ConsoleTraceReporter:
    def __init__(self, config: TraceRunConfig) -> None:
        self.config = config
        self._flushed_stages: set[str] = set()
        self._run_start_ms: float | None = None

    def mark_run_start(self) -> None:
        import time

        self._run_start_ms = time.perf_counter()

    def flush_stage(self, stage_id: str, state: AgentState) -> None:
        if stage_id in self._flushed_stages:
            return
        self._flushed_stages.add(stage_id)
        events = list(state.get("trace_events") or [])
        stage_events = [e for e in events if e.stage_id == stage_id]
        reg = ASK_TRACE_REGISTRY.get(stage_id)
        if reg is None:
            return
        if self.config.emit_jsonl:
            for ev in stage_events:
                sys.stderr.write(ev.model_dump_json() + "\n")
                sys.stderr.flush()
        if not self.config.show_human:
            return
        lines = reg.renderer(stage_id, state, stage_events, self.config)
        self._write_panel(reg.title, lines)

    def write_summary(
        self,
        *,
        status: str,
        citation_count: int,
        total_ms: int | None = None,
    ) -> None:
        if not self.config.show_human:
            return
        parts = [f"status={status}", f"citations={citation_count}"]
        if total_ms is not None:
            parts.append(f"total={total_ms} ms")
        self._write_panel("Trace summary", [" ".join(parts)])

    def _write_panel(self, title: str, lines: list[str]) -> None:
        body = "\n".join(lines)
        if self.config.use_color and self.config.panel_enabled:
            try:
                from rich.console import Console
                from rich.panel import Panel

                console = Console(file=sys.stderr, stderr=True, highlight=False)
                console.print(Panel(body, title=title, border_style="cyan"))
                return
            except Exception:
                pass
        sys.stderr.write(f"\n--- {title} ---\n{body}\n")
        sys.stderr.flush()

    def render_all_normalized(self, state: AgentState) -> str:
        """Plain-text aggregate for tests (no ANSI)."""
        parts: list[str] = []
        for reg in sorted(ASK_TRACE_REGISTRY.values(), key=lambda r: r.order):
            sid = reg.stage_id
            events = [e for e in state.get("trace_events") or [] if e.stage_id == sid]
            if not events:
                continue
            lines = reg.renderer(sid, state, events, self.config)
            parts.append(f"--- {reg.title} ---")
            parts.extend(lines)
        return "\n".join(parts)

    def events_by_stage(self, state: AgentState) -> dict[str, list[TraceEvent]]:
        grouped: dict[str, list[TraceEvent]] = defaultdict(list)
        for ev in state.get("trace_events") or []:
            grouped[ev.stage_id].append(ev)
        return grouped
