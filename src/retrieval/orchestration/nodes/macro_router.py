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
from retrieval.orchestration.state import AgentState


def macro_router(state: AgentState, *, graph_api=None) -> dict:
    query = state["query"]
    snapshot_id = state["snapshot_id"]
    filings: list[FilingRef] = []
    if graph_api is not None:
        snap = graph_api.get_snapshot(snapshot_id)
        filings = list(snap.manifest.filing_refs)

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
    resp = llm.invoke(
        [
            SystemMessage(content="You are a financial disclosure routing agent."),
            HumanMessage(content=prompt),
        ]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"intent_summary": query, "comparison_mode": "YoY"}

    selected = filings
    plan = MacroPlan(
        intent_summary=data.get("intent_summary", query),
        temporal_scope=TemporalScope(
            anchor_periods=[filings[-1].period_end] if filings else [date.today()],
            comparison_mode=ComparisonMode(data.get("comparison_mode", "YoY")),
        ),
        rationale=text[:500],
    )
    return {
        "macro_plan": plan,
        "filing_set": selected,
        "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
    }
