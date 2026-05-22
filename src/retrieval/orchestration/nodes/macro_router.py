"""Macro routing: temporal scope and filing selection."""

from __future__ import annotations

import json
import os
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from models.enums import ComparisonMode
from models.filing import FilingRef
from models.query import MacroPlan, TemporalScope
from retrieval.orchestration.llm import create_chat_llm
from tracing.console_trace.llm import traced_llm_invoke
from retrieval.orchestration.state import AgentState


def _extract_json_from_llm(text: str) -> dict:
    """Parse JSON from LLM output (handles markdown fences and preamble)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = stripped.find("{"), stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(stripped[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def _parse_comparison_mode(value: object) -> ComparisonMode:
    if value is None:
        return ComparisonMode.YOY
    raw = str(value).strip()
    if not raw:
        return ComparisonMode.YOY
    normalized = raw.lower().replace("-", "").replace("_", "")
    if normalized in ("yoy", "yearoveryear", "yearonyear"):
        return ComparisonMode.YOY
    if normalized in ("qoq", "quarteroverquarter"):
        return ComparisonMode.QOQ
    if normalized in ("sequential", "seq", "periodoverperiod"):
        return ComparisonMode.SEQUENTIAL
    try:
        return ComparisonMode(raw)
    except ValueError:
        return ComparisonMode.YOY


def macro_router(state: AgentState, *, graph_api=None) -> dict:
    query = state["query"]
    snapshot_id = state["snapshot_id"]
    pre_bound = list(state.get("filing_set") or [])
    filings: list[FilingRef] = pre_bound
    if graph_api is not None and not filings:
        snap = graph_api.get_snapshot(snapshot_id)
        filings = list(snap.manifest.filing_refs)

    if pre_bound:
        plan = MacroPlan(
            intent_summary=query[:200],
            temporal_scope=TemporalScope(
                anchor_periods=[pre_bound[0].period_end] if pre_bound else [],
                comparison_mode=ComparisonMode.YOY,
            ),
            rationale="pre-bound filing set from corpus temporal resolver",
        )
        return {
            "macro_plan": plan,
            "filing_set": pre_bound,
            "macro_llm_skipped": True,
            "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
        }

    if os.environ.get("USE_MOCK_LLM", "0") == "1" or not filings:
        plan = MacroPlan(
            intent_summary=query[:200],
            temporal_scope=TemporalScope(
                anchor_periods=[date.today()],
                comparison_mode=ComparisonMode.YOY,
            ),
            rationale="mock macro routing",
        )
        return {
            "macro_plan": plan,
            "filing_set": filings or [],
            "macro_llm_skipped": True,
            "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
        }

    llm = create_chat_llm()
    filings_json = json.dumps([f.model_dump(mode="json") for f in filings], default=str)[:800]
    prompt = (
        f"Question: {query}\n"
        f"Available filings: {filings_json}\n"
        "Return JSON with intent_summary, comparison_mode (YoY|QoQ|sequential), "
        "and accession numbers to use."
    )
    messages = [
        SystemMessage(content="You are a financial disclosure routing agent."),
        HumanMessage(content=prompt),
    ]
    resp, trace_patch = traced_llm_invoke("macro_router", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    data = _extract_json_from_llm(text)
    if not data:
        data = {"intent_summary": query, "comparison_mode": "YoY"}

    selected = filings
    plan = MacroPlan(
        intent_summary=str(data.get("intent_summary") or query),
        temporal_scope=TemporalScope(
            anchor_periods=[filings[-1].period_end] if filings else [date.today()],
            comparison_mode=_parse_comparison_mode(data.get("comparison_mode")),
        ),
        rationale=text[:500],
    )
    out = {
        "macro_plan": plan,
        "filing_set": selected,
        "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
    }
    if trace_patch.get("trace_events"):
        out["trace_events"] = trace_patch["trace_events"]
    return out
