"""XBRL fact resolution prompt helpers (023 M2)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent


def min_facts_required(metric_intent: MetricIntent | None) -> int:
    if metric_intent is None:
        return 1
    if metric_intent.metric_type in ("ratio", "delta", "percent_change"):
        return 2
    if metric_intent.periods_needed >= 2:
        return 2
    return 1


def resolution_selection_instructions(
    metric_intent: MetricIntent | None,
    *,
    forbidden_patterns: list[str],
) -> str:
    min_facts = min_facts_required(metric_intent)
    lines = [
        f"Select exactly {min_facts} catalog fact(s) when sufficient=true.",
    ]
    if metric_intent and metric_intent.metric_type == "ratio":
        lines.append(
            "For ratio metrics return selected_chunk_ids as [numerator_id, denominator_id] "
            "for the same fiscal period."
        )
    elif min_facts >= 2:
        lines.append(
            "For delta/percent-change metrics return two ids ordered newest period first."
        )
    if forbidden_patterns:
        lines.append(
            "Do NOT select concepts containing: "
            + ", ".join(forbidden_patterns[:12])
            + "."
        )
    lines.append("Set sufficient=false when required facts are missing from the catalog.")
    return "\n".join(lines)
