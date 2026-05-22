"""Meso routing: section-level graph navigation."""

from __future__ import annotations

from models.query import SectionCandidate
from retrieval.orchestration.state import AgentState


def meso_router(state: AgentState, *, graph_api) -> dict:
    snapshot_id = state["snapshot_id"]
    filings = state.get("filing_set") or []
    query = state["query"].lower()
    intent_trace = state.get("intent_trace")
    prefer_html = intent_trace is not None and intent_trace.query_intent.value in (
        "qualitative",
        "hybrid",
    )

    sections = graph_api.sections_for_filings(snapshot_id, filings)
    candidates: list[SectionCandidate] = []
    visits = []

    for sec in sections:
        score = 1.0 if any(k in sec.label.lower() for k in query.split()[:5]) else 0.3
        if any(
            k in sec.label.lower()
            for k in ("financial", "balance", "income", "cash", "liquidity", "margin")
        ):
            score += 0.4
        if any(k in query for k in ("revenue", "sales", "driver", "segment", "growth")):
            if any(
                k in sec.label.lower()
                for k in (
                    "revenue",
                    "management",
                    "md&a",
                    "results",
                    "operations",
                    "business",
                    "xbrl",
                    "financial facts",
                )
            ):
                score += 0.5
        if "xbrl" in sec.label.lower() and any(
            k in query for k in ("revenue", "sales", "income", "assets", "cash", "earnings")
        ):
            score += 2.0
        if prefer_html and (
            "html-" in sec.node_id or sec.properties.get("source_type") == "HTML"
        ):
            score += 2.5
        if prefer_html and any(k in query for k in ("risk", "factor")):
            if any(
                k in sec.label.lower() or str(sec.properties.get("section_id", ""))
                for k in ("risk", "1a", "html-risk")
            ):
                score += 3.0
        if prefer_html and any(
            k in sec.label.lower() for k in ("risk", "management", "md&a", "business", "item 7")
        ):
            score += 0.8
        if prefer_html and any(
            f.form_type == "10-K" and f.accession in sec.node_id for f in filings
        ):
            score += 1.0
        candidates.append(
            SectionCandidate(section_node_id=sec.node_id, score=score, path=[sec.node_id])
        )
        visits.append({"node_id": sec.node_id, "stage": "meso"})

    candidates.sort(key=lambda c: c.score, reverse=True)
    return {
        "section_candidates": candidates[:10],
        "graph_traversal": visits,
    }


def rank_sections_heuristic(state: AgentState, graph_api) -> dict:
    return meso_router(state, graph_api=graph_api)
