"""Thread-local console trace reporter context."""

from __future__ import annotations

import contextvars

from tracing.console_trace.reporter import ConsoleTraceReporter

_reporter_var: contextvars.ContextVar[ConsoleTraceReporter | None] = contextvars.ContextVar(
    "console_trace_reporter",
    default=None,
)


def set_trace_reporter(reporter: ConsoleTraceReporter | None) -> None:
    _reporter_var.set(reporter)


def get_trace_reporter() -> ConsoleTraceReporter | None:
    return _reporter_var.get()
