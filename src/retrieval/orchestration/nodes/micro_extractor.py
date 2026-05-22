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
from parsing.xbrl_facts import concepts_for_query
from retrieval.evidence_scope import (
    allowed_document_ids,
    anchor_period_ends,
    node_in_allowed_documents,
    period_alignment_score,
)
from retrieval.orchestration.state import AgentState

_FINANCIAL_QUERY = re.compile(
    r"\b(revenue|sales|income|earnings|profit|assets|liabilities|cash|eps|margin|"
    r"debt|dividend|shares|cost|expense|growth|yoy|qoq|billion|million|\$)\b",
    re.I,
)


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    snapshot_id = state["snapshot_id"]
    candidates = state.get("section_candidates") or []
    query = state.get("query", "")
    filing_set: list[FilingRef] = list(state.get("filing_set") or [])
    snap = graph_api.get_snapshot(snapshot_id)
    visits = []

    section_ids = {c.section_node_id for c in candidates[:5]}
    query_pat = concepts_for_query(query)
    is_financial = bool(_FINANCIAL_QUERY.search(query))
    intent_trace = state.get("intent_trace")
    bias = intent_trace.source_bias_applied if intent_trace else SourceBias.BLENDED
    query_intent = intent_trace.query_intent if intent_trace else None
    qualitative_only = query_intent == QueryIntent.QUALITATIVE
    doc_ids = allowed_document_ids(filing_set)
    anchors = anchor_period_ends(filing_set)

    scored: list[tuple[float, EvidenceChunk]] = []

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

        score = _relevance_score(query, excerpt, node.label, query_pat)
        score += _qualitative_keyword_boost(query, excerpt, node_source)
        if is_xbrl_fact:
            score += 2.0
            score += period_alignment_score(excerpt, anchors)
        if is_financial and is_xbrl_fact:
            score += 3.0

        score *= _source_bias_multiplier(node_source, bias)
        if qualitative_only and node_source == EvidenceSourceType.HTML:
            score += 5.0
            if "risk_factors" in str(node.properties.get("section_id", "")):
                score += 8.0
            if len(excerpt) > 3000:
                score += 3.0

        if score < 0:
            continue

        accession = _accession_from_node_id(node.node_id)
        section_id = str(node.properties.get("section_id", ""))
        chunk = EvidenceChunk(
            chunk_node_id=node.node_id,
            excerpt=excerpt[:2000],
            content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
            citation_label=_citation_label(node, excerpt),
            source_type=node_source,
            accession=accession,
            section_id=section_id,
        )
        scored.append((score, chunk))
        visit: dict = {"node_id": node.node_id, "stage": "micro"}
        doc_id = _document_root_id(node.node_id)
        if doc_id and hasattr(graph_api, "shortest_structural_path"):
            path = graph_api.shortest_structural_path(snapshot_id, doc_id, node.node_id)
            if path:
                visit["path_node_ids"] = path[0]
                visit["path_edge_types"] = path[1]
        visits.append(visit)

    scored.sort(key=lambda x: -x[0])
    evidence = [c for _, c in scored[:20]]
    evidence = _ensure_hybrid_html(evidence, scored, bias)

    return {"evidence_chunks": evidence, "graph_traversal": visits}


def _node_source_type(node) -> EvidenceSourceType:
    raw = str(node.properties.get("source_type", "")).upper()
    if raw == EvidenceSourceType.HTML.value:
        return EvidenceSourceType.HTML
    if "html-" in node.node_id:
        return EvidenceSourceType.HTML
    return EvidenceSourceType.XBRL


def _source_bias_multiplier(source: EvidenceSourceType, bias: SourceBias) -> float:
    if bias == SourceBias.XBRL_PRIMARY:
        return 1.5 if source == EvidenceSourceType.XBRL else 0.7
    if bias == SourceBias.HTML_PRIMARY:
        return 1.5 if source == EvidenceSourceType.HTML else 0.7
    return 1.0


def _accession_from_node_id(node_id: str) -> str:
    m = re.search(r"doc-(\d{10}-\d{2}-\d{6})", node_id)
    return m.group(1) if m else ""


def _ensure_hybrid_html(
    evidence: list[EvidenceChunk],
    scored: list[tuple[float, EvidenceChunk]],
    bias: SourceBias,
) -> list[EvidenceChunk]:
    if bias != SourceBias.BLENDED:
        return evidence
    if any(c.source_type == EvidenceSourceType.HTML for c in evidence):
        return evidence
    for _, chunk in scored:
        if chunk.source_type == EvidenceSourceType.HTML:
            evidence = list(evidence)
            evidence.append(chunk)
            return evidence[:20]
    return evidence


def _qualitative_keyword_boost(
    query: str,
    excerpt: str,
    source: EvidenceSourceType,
) -> float:
    if source != EvidenceSourceType.HTML:
        return 0.0
    q = query.lower()
    ex = excerpt.lower()
    boost = 0.0
    if "risk" in q and "risk" in ex:
        boost += 10.0
    if any(k in q for k in ("md&a", "management", "liquidity", "outlook")) and any(
        k in ex for k in ("management", "md&a", "discussion", "liquidity")
    ):
        boost += 6.0
    if "business" in q and "business" in ex:
        boost += 4.0
    return boost


def _relevance_score(
    query: str,
    excerpt: str,
    label: str,
    query_pat: re.Pattern[str] | None,
) -> float:
    q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    text = f"{excerpt} {label}".lower()
    score = sum(0.25 for t in q_tokens if t in text and len(t) > 2)
    if query_pat and query_pat.search(excerpt):
        score += 5.0
    if re.search(r"\$[\d,.]+ (billion|million)", excerpt):
        score += 1.0
    if label.startswith("table-") and "value:" not in excerpt:
        score -= 1.0
    return score


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
