"""Trajectory validation + judge console footer (010)."""

from __future__ import annotations

from evaluation.ask_judge import PostQueryAuditResult
from tracing.console_trace.reporter import ConsoleTraceReporter


def emit_trajectory_audit_footer(
    reporter: ConsoleTraceReporter,
    audit: PostQueryAuditResult,
) -> None:
    if not reporter.config.show_human:
        return
    lines = ["validation: " + audit.validation_status.value]
    summary = audit.judge_summary
    if summary is None:
        reporter.write_audit_panel(lines)
        return
    lines.append(f"judge: {summary.judge_status.value} ({summary.judge_model})")
    for c in summary.criteria:
        stage = f" [{c.stage}]" if c.stage else ""
        lines.append(f"  {c.criterion_id}: {c.score:.2f}{stage}")
    if summary.weakest_criterion_id:
        ws = summary.weakest_stage or "n/a"
        lines.append(f"weakest: {summary.weakest_criterion_id} @ {ws}")
    if summary.judge_status.value == "degraded" and summary.error:
        lines.append(f"warning: judge degraded — {summary.error[:120]}")
    reporter.write_audit_panel(lines[:15])
