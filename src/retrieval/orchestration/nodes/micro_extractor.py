"""Micro routing: query-relevant chunk and XBRL fact extraction."""

from __future__ import annotations

import hashlib
import re

from models.enums import (
    EvidenceSourceType,
    GraphEdgeType,
    GraphNodeType,
    QueryIntent,
    SourceBias,
)
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.evidence_scope import (
    allowed_document_ids,
    anchor_period_ends,
    node_in_allowed_documents,
)
from retrieval.orchestration.micro_scoring import (
    is_financial_query,
    rank_trace_row,
    score_chunk,
    source_bias_multiplier as _source_bias_multiplier,
)
from retrieval.orchestration.state import AgentState


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    snapshot_id = state["snapshot_id"]
    candidates = state.get("section_candidates") or []
    query = state.get("query", "")
    filing_set: list[FilingRef] = list(state.get("filing_set") or [])
    snap = graph_api.get_snapshot(snapshot_id)
    visits = []
    path_by_chunk: dict[str, list[str]] = {}

    section_ids = {c.section_node_id for c in candidates[:5]}
    is_financial = is_financial_query(query)
    intent_trace = state.get("intent_trace")
    bias = intent_trace.source_bias_applied if intent_trace else SourceBias.BLENDED
    query_intent = intent_trace.query_intent if intent_trace else None
    qualitative_only = query_intent == QueryIntent.QUALITATIVE
    doc_ids = allowed_document_ids(filing_set)
    anchors = anchor_period_ends(filing_set)

    scored: list[tuple[float, EvidenceChunk, dict]] = []

    for node in snap.nodes:
        if node.node_type not in (
            GraphNodeType.CHUNK_TABLE,
            GraphNodeType.CHUNK_ROW,
            GraphNodeType.CHUNK_PARAGRAPH,
            GraphNodeType.CHUNK_XBRL_FACT,
        ):
            continue

        if doc_ids and not node_in_allowed_documents(node.node_id, doc_ids):
            continue

        excerpt = (node.source_ref or node.label or "").strip()
        if not excerpt:
            continue

        parent_section = _parent_section(snap, node.node_id)
        is_xbrl_fact = (
            node.node_type == GraphNodeType.CHUNK_XBRL_FACT
            or excerpt.startswith("XBRL ")
            or "xbrl-" in node.node_id
        )
        node_source = _node_source_type(node)

        if qualitative_only and is_xbrl_fact:
            continue

        html_section_gate = (
            parent_section in section_ids
            or "html-" in (parent_section or "")
            or "html-" in node.node_id
        )
        if section_ids and not html_section_gate and not is_xbrl_fact:
            continue

        section_id = str(node.properties.get("section_id", ""))
        score, components = score_chunk(
            query=query,
            excerpt=excerpt,
            label=node.label or "",
            node_source=node_source,
            is_xbrl_fact=is_xbrl_fact,
            is_financial_query=is_financial,
            qualitative_only=qualitative_only,
            section_id=section_id,
            bias=bias,
            anchors=anchors,
        )
        if score < 0:
            continue

        accession = _accession_from_node_id(node.node_id)
        chunk = EvidenceChunk(
            chunk_node_id=node.node_id,
            excerpt=excerpt[:2000],
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
            citation_label=_citation_label(node, excerpt),
            source_type=node_source,
            accession=accession,
            section_id=section_id,
        )
        scored.append((score, chunk, components))
        visit: dict = {"node_id": node.node_id, "stage": "micro"}
        doc_id = _document_root_id(node.node_id)
        if doc_id and hasattr(graph_api, "shortest_structural_path"):
            path = graph_api.shortest_structural_path(snapshot_id, doc_id, node.node_id)
            if path:
                visit["path_node_ids"] = path[0]
                visit["path_edge_types"] = path[1]
                path_by_chunk[node.node_id] = list(path[1])
        visits.append(visit)

    scored.sort(key=lambda x: -x[0])
    ranked_count = len(scored)
    evidence = [c for _, c, _ in scored[:20]]
    evidence = _ensure_hybrid_html(evidence, scored, bias)

    cfg_excerpt = 400
    try:
        from tracing.console_trace.config import load_trace_config

        cfg_excerpt = int(load_trace_config().get("excerpt_preview_chars", 400))
    except Exception:
        pass

    rank_trace: list[dict] = []
    for score, chunk, components in scored[:10]:
        preview = chunk.excerpt[:cfg_excerpt] + (
            "..." if len(chunk.excerpt) > cfg_excerpt else ""
        )
        rank_trace.append(
            rank_trace_row(
                chunk_node_id=chunk.chunk_node_id,
                source_type=getattr(chunk.source_type, "value", str(chunk.source_type)),
                section_id=chunk.section_id,
                score=score,
                components=components,
                excerpt_preview=preview,
                structural_path=path_by_chunk.get(chunk.chunk_node_id),
            )
        )

    return {
        "evidence_chunks": evidence,
        "graph_traversal": visits,
        "micro_ranked_count": ranked_count,
        "micro_rank_trace": rank_trace,
    }


def _node_source_type(node) -> EvidenceSourceType:
    raw = str(node.properties.get("source_type", "")).upper()
    if raw == EvidenceSourceType.HTML.value:
        return EvidenceSourceType.HTML
    if "html-" in node.node_id:
        return EvidenceSourceType.HTML
    return EvidenceSourceType.XBRL


def _accession_from_node_id(node_id: str) -> str:
    m = re.search(r"doc-(\d{10}-\d{2}-\d{6})", node_id)
    return m.group(1) if m else ""


def _ensure_hybrid_html(
    evidence: list[EvidenceChunk],
    scored: list[tuple[float, EvidenceChunk, dict]],
    bias: SourceBias,
) -> list[EvidenceChunk]:
    if bias != SourceBias.BLENDED:
        return evidence
    if any(c.source_type == EvidenceSourceType.HTML for c in evidence):
        return evidence
    for _, chunk, _ in scored:
        if chunk.source_type == EvidenceSourceType.HTML:
            evidence = list(evidence)
            evidence.append(chunk)
            return evidence[:20]
    return evidence


def _citation_label(node, excerpt: str) -> str:
    if excerpt.startswith("XBRL "):
        return excerpt.split(":", 1)[0].replace("XBRL ", "")[:80]
    return (node.label or "evidence")[:80]


def _document_root_id(node_id: str) -> str | None:
    m = re.match(r"^(doc-\d{10}-\d{2}-\d{6})", node_id)
    return m.group(1) if m else None


def _parent_section(snap, node_id: str) -> str | None:
    for edge in snap.edges:
        if edge.target_id == node_id and edge.edge_type == GraphEdgeType.CONTAINS:
            for n in snap.nodes:
                if n.node_id == edge.source_id and n.node_type == GraphNodeType.SECTION:
                    return n.node_id
            if edge.source_id.startswith("doc-"):
                return edge.source_id
    return None
