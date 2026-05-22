"""Meso routing: section-level graph navigation."""

from __future__ import annotations

from models.query import SectionCandidate
from retrieval.orchestration.meso_scoring import score_section, section_trace_row
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
    accessions = [f.accession for f in filings]

    sections = graph_api.sections_for_filings(snapshot_id, filings)
    candidates: list[SectionCandidate] = []
    section_trace: list[dict] = []
    visits = []

    for sec in sections:
        section_id = str(sec.properties.get("section_id", ""))
        score, components = score_section(
            label=sec.label,
            node_id=sec.node_id,
            section_id=section_id,
            query=query,
            prefer_html=prefer_html,
            filing_accessions=accessions,
        )
        candidates.append(
            SectionCandidate(section_node_id=sec.node_id, score=score, path=[sec.node_id])
        )
        section_trace.append(
            section_trace_row(
                section_node_id=sec.node_id,
                label=sec.label,
                section_id=section_id,
                score=score,
                components=components,
                path=[sec.node_id],
            )
        )
        visits.append({"node_id": sec.node_id, "stage": "meso"})

    candidates.sort(key=lambda c: c.score, reverse=True)
    section_trace.sort(key=lambda r: r["score"], reverse=True)
    return {
        "section_candidates": candidates[:10],
        "meso_section_trace": section_trace[:10],
        "graph_traversal": visits,
    }


def rank_sections_heuristic(state: AgentState, graph_api) -> dict:
    return meso_router(state, graph_api=graph_api)
