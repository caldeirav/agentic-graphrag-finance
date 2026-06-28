"""Regression: ratio answers must not use dollar amounts for rate/margin/payout (022-A)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.numeric_computation import compute_numeric_answer
from retrieval.skills.ratio_pair_resolution import resolve_ratio_pair
from retrieval.skills.structured_answer import StructuredAnswerPayload
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult

_TARGETS = Path(__file__).resolve().parents[3] / "specs/022-outcome-score-ladder/fixtures/cohort_phase_targets.json"
_FORBIDDEN = json.loads(_TARGETS.read_text(encoding="utf-8"))["phase_a_ratio"]["forbidden_answer_patterns"]


def _entry(cid: str, concept: str, value: str) -> XbrlFactCatalogEntry:
    return XbrlFactCatalogEntry(
        chunk_id=cid,
        concept=concept,
        value_display=value,
        period_start="2025-01-01",
        period_end="2025-12-31",
        is_annual=True,
        matches_query=True,
    )


@pytest.mark.parametrize(
    "query,intent_label",
    [
        ("Net profit margin fiscal year 2025", "margin"),
        ("Effective tax rate fiscal year 2025", "tax"),
        ("Dividend payout ratio fiscal year 2025", "payout"),
    ],
)
def test_ratio_payload_has_percent_not_dollars(query: str, intent_label: str) -> None:
    if intent_label == "margin":
        catalog = [
            _entry("ni", "NetIncomeLoss", "$36.00 billion"),
            _entry("rev", "Revenues", "$413.00 billion"),
        ]
    elif intent_label == "tax":
        catalog = [
            _entry("tax", "IncomeTaxExpense", "$8.67 billion"),
            _entry("pretax", "IncomeBeforeIncomeTaxes", "$40.00 billion"),
        ]
    else:
        catalog = [
            _entry("div", "DividendsPaid", "$16.00 billion"),
            _entry("ni", "NetIncomeLoss", "$36.00 billion"),
        ]
    intent = MetricIntent(metric_type="ratio", metric_label=query, periods_needed=1)
    pair = resolve_ratio_pair(catalog, intent, query)
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=[
            pair.numerator_entry.chunk_id,
            pair.denominator_entry.chunk_id,
        ]
        if pair.numerator_entry and pair.denominator_entry
        else [],
        sufficient=pair.sufficient,
    )
    payload = compute_numeric_answer(intent, resolution, catalog, query=query)
    assert payload is not None
    assert not payload.abstain
    assert payload.value.endswith("%")
    for pat in _FORBIDDEN:
        assert not re.search(pat, payload.value, re.I)


def test_structured_render_ratio_no_dollar_rate() -> None:
    payload = StructuredAnswerPayload(
        metric_label="Effective tax rate",
        value="21.68%",
        unit="percent",
        citation_chunk_ids=["a", "b"],
        confidence="high",
        abstain=False,
        metric_type="ratio",
    )
    from retrieval.skills.structured_answer import render_structured_answer

    text = render_structured_answer(payload)
    assert "21.68%" in text
    assert not re.search(r"rate was \$", text, re.I)
