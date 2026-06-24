"""Numeric question metric typing (021)."""

from __future__ import annotations

import json
import os
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.orchestration.llm import create_chat_llm
from tracing.console_trace.llm import traced_llm_invoke

MetricType = Literal["point", "delta", "ratio", "percent_change"]


class MetricIntent(BaseModel):
    metric_type: MetricType = "point"
    metric_label: str = ""
    required_concepts: list[str] = Field(default_factory=list)
    periods_needed: int = 1
    formula: str = ""


def heuristic_metric_intent(query: str) -> MetricIntent:
    """Deterministic metric typing without LLM (repro slice expansion, tests)."""
    return _heuristic_metric_intent(query)


def _heuristic_metric_intent(query: str) -> MetricIntent:
    q = query.lower()
    label = query.strip()[:120]
    if "effective tax rate" in q or ("tax rate" in q and "effective" in q):
        return MetricIntent(
            metric_type="ratio",
            metric_label=label,
            periods_needed=1,
            formula="tax_expense/pretax_income*100",
            required_concepts=["IncomeTaxExpense", "EarningsBeforeIncomeTax"],
        )
    if "dividend payout" in q or ("dividend" in q and "payout" in q):
        return MetricIntent(
            metric_type="ratio",
            metric_label=label,
            periods_needed=1,
            formula="dividends/net_income*100",
            required_concepts=["Dividends", "NetIncome"],
        )
    if any(k in q for k in ("margin", "ratio", " divided by ", " divide ", " as a percentage of")):
        return MetricIntent(
            metric_type="ratio",
            metric_label=label,
            periods_needed=1,
            formula="numerator/denominator*100",
            required_concepts=["Income", "Revenue"],
        )
    if any(
        k in q
        for k in (
            "year-over-year",
            "year over year",
            "yoy",
            "percentage change",
            "percent change",
            "% change",
            "percentage decrease",
            "percentage increase",
        )
    ):
        return MetricIntent(
            metric_type="percent_change",
            metric_label=label,
            periods_needed=2,
            formula="(new-old)/abs(old)*100",
        )
    if any(k in q for k in ("change in", "change from", "increase in", "decrease in", "delta")):
        return MetricIntent(
            metric_type="delta",
            metric_label=label,
            periods_needed=2,
            formula="new-old",
        )
    return MetricIntent(metric_type="point", metric_label=label, periods_needed=1)


def classify_metric_intent(query: str) -> tuple[MetricIntent, dict]:
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _heuristic_metric_intent(query), {}
    llm = create_chat_llm()
    prompt = (
        f"Question: {query}\n"
        "Classify numeric intent. Return JSON:\n"
        '{"metric_type":"point|delta|ratio|percent_change","metric_label":str,'
        '"required_concepts":[str],"periods_needed":1|2,"formula":str}\n'
    )
    messages = [
        SystemMessage(content="Financial metric classifier. JSON only."),
        HumanMessage(content=prompt),
    ]
    resp, trace = traced_llm_invoke("metric_intent", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    data = extract_json_from_llm(text)
    if not data:
        return _heuristic_metric_intent(query), trace
    try:
        return MetricIntent.model_validate(data), trace
    except Exception:
        return _heuristic_metric_intent(query), trace
