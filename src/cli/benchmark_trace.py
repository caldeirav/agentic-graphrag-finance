"""Rich console tracing for benchmark-dataset generation (011)."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import StrEnum

from tracing.console_trace.config import build_trace_run_config, resolve_trace_level


class BenchmarkTraceLevel(StrEnum):
    QUIET = "quiet"
    NORMAL = "normal"
    VERBOSE = "verbose"


@dataclass
class BenchmarkTraceReporter:
    """Structured stderr progress for generate / publish workflows."""

    level: BenchmarkTraceLevel = BenchmarkTraceLevel.NORMAL
    use_color: bool = True
    panel_enabled: bool = True
    _phase_timer: float | None = field(default=None, init=False, repr=False)
    _item_timer: float | None = field(default=None, init=False, repr=False)
    _lines: list[str] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def from_cli(cls, trace: str | None) -> BenchmarkTraceReporter:
        level = BenchmarkTraceLevel(resolve_trace_level(trace).value)
        cfg = build_trace_run_config(resolve_trace_level(trace))
        return cls(
            level=level,
            use_color=cfg.use_color,
            panel_enabled=cfg.panel_enabled,
        )

    def _emit(self, message: str, *, panel_title: str | None = None) -> None:
        if self.level == BenchmarkTraceLevel.QUIET:
            return
        if panel_title and self.panel_enabled:
            try:
                from rich.console import Console
                from rich.panel import Panel

                console = Console(file=sys.stderr, stderr=True, highlight=False)
                console.print(Panel(message, title=panel_title, border_style="green"))
                return
            except Exception:
                pass
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def log(self, message: str) -> None:
        if self.level == BenchmarkTraceLevel.QUIET:
            return
        sys.stderr.write(f"[benchmark-dataset] {message}\n")
        sys.stderr.flush()
        self._lines.append(message)

    def phase_start(self, phase: str, detail: str = "") -> None:
        self._phase_timer = time.perf_counter()
        suffix = f" — {detail}" if detail else ""
        self.log(f"▶ phase {phase}{suffix}")

    def phase_end(self, phase: str, detail: str = "") -> None:
        elapsed_ms = 0
        if self._phase_timer is not None:
            elapsed_ms = int((time.perf_counter() - self._phase_timer) * 1000)
        suffix = f" — {detail}" if detail else ""
        self.log(f"✓ phase {phase} complete ({elapsed_ms} ms){suffix}")

    def item_start(self, seq: int, profile: str) -> None:
        self._item_timer = time.perf_counter()
        self.log(f"  · item {seq} [{profile}] generating…")

    def item_end(
        self,
        item_id: str,
        status: str,
        errors: list[str] | None = None,
    ) -> None:
        elapsed_ms = 0
        if self._item_timer is not None:
            elapsed_ms = int((time.perf_counter() - self._item_timer) * 1000)
        err = f" errors={errors}" if errors else ""
        self.log(f"  · item {item_id} → {status} ({elapsed_ms} ms){err}")

    def gemini_call(
        self,
        *,
        profile: str,
        attempt: int,
        model: str,
        duration_ms: int,
        preview: str = "",
    ) -> None:
        if self.level == BenchmarkTraceLevel.QUIET:
            return
        head = f"  ↳ Gemini {model} profile={profile} attempt={attempt + 1} ({duration_ms} ms)"
        if self.level == BenchmarkTraceLevel.VERBOSE and preview:
            clipped = preview[:600].replace("\n", " ")
            self.log(f"{head}\n    prompt/response preview: {clipped}…")
        else:
            self.log(head)

    def budget(self, message: str) -> None:
        self.log(f"  budget: {message}")

    def summary(self, title: str, lines: list[str]) -> None:
        body = "\n".join(lines)
        self._emit(body, panel_title=title)
