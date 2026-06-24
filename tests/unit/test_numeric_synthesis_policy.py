"""Unit tests for numeric synthesis path policy (023 M1)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.numeric_synthesis_policy import (
    is_numeric_metric_type,
    should_block_numeric_llm_fallback,
)


def test_is_numeric_metric_type_covers_all_numeric_kinds() -> None:
    for metric_type in ("point", "delta", "ratio", "percent_change"):
        assert is_numeric_metric_type(MetricIntent(metric_type=metric_type)) is True


def test_should_block_only_with_xbrl_evidence() -> None:
    intent = MetricIntent(metric_type="ratio", metric_label="margin")
    assert should_block_numeric_llm_fallback(intent, has_xbrl_evidence=True) is True
    assert should_block_numeric_llm_fallback(intent, has_xbrl_evidence=False) is False
