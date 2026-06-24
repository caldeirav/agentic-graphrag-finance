"""Numeric synthesis path policy (023 M1)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent, MetricType

NUMERIC_METRIC_TYPES: frozenset[MetricType] = frozenset(
    {"point", "delta", "ratio", "percent_change"}
)


def is_numeric_metric_type(metric_intent: MetricIntent) -> bool:
    return metric_intent.metric_type in NUMERIC_METRIC_TYPES


def should_block_numeric_llm_fallback(
    metric_intent: MetricIntent,
    *,
    has_xbrl_evidence: bool,
) -> bool:
    """Block structured/live LLM when XBRL evidence exists and intent is numeric."""
    return has_xbrl_evidence and is_numeric_metric_type(metric_intent)
