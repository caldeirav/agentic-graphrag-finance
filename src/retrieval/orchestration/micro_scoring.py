"""Heuristic chunk scoring for micro extractor (with trace components)."""

from __future__ import annotations

import re
from typing import Any

from models.enums import EvidenceSourceType, SourceBias
from parsing.xbrl_facts import (
    concepts_for_query,
    is_revenue_concept,
    is_revenue_query,
    is_securities_sales_false_positive,
)
from retrieval.evidence_scope import period_alignment_score
from retrieval.orchestration.meso_scoring import is_mda_query

_FINANCIAL_QUERY = re.compile(
    r"\b(revenue|sales|income|earnings|profit|assets|liabilities|cash|eps|margin|"
    r"debt|dividend|shares|cost|expense|growth|yoy|qoq|billion|million|\$)\b",
    re.I,
)
_RISK_QUERY = re.compile(r"\b(risk|factor|factors|1a)\b", re.I)
_RISK_CROSS_REF = re.compile(
    r"item\s+1a\s+of\s+this\s+form\s+10-?k\s+under\s+the\s+heading",
    re.I,
)
_OFF_TOPIC_RISK_CHUNK = re.compile(
    r"(operating\s+expenses\s+for\s+\d{4}|internal\s+control\s+–\s+integrated\s+framework|"
    r"share-based\s+compensation\s+expense|item\s+2\.\s+properties|basis\s+for\s+opinion)",
    re.I,
)


def is_financial_query(query: str) -> bool:
    return bool(_FINANCIAL_QUERY.search(query))


def source_bias_multiplier(source: EvidenceSourceType, bias: SourceBias) -> float:
    if bias == SourceBias.XBRL_PRIMARY:
        return 1.5 if source == EvidenceSourceType.XBRL else 0.7
    if bias == SourceBias.HTML_PRIMARY:
        return 1.5 if source == EvidenceSourceType.HTML else 0.7
    return 1.0


def relevance_score(
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


def qualitative_keyword_boost(
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
    if any(
        k in q
        for k in (
            "md&a",
            "mda",
            "management discussion",
            "management's discussion",
        )
    ) and any(k in ex for k in ("management", "md&a", "discussion", "analysis", "liquidity")):
        boost += 10.0
    elif any(k in q for k in ("management", "liquidity", "outlook")) and any(
        k in ex for k in ("management", "md&a", "discussion", "liquidity")
    ):
        boost += 6.0
    if "business" in q and "business" in ex:
        boost += 4.0
    return boost


def risk_excerpt_score_adjustment(excerpt: str, section_id: str, *, query: str = "") -> float:
    ex = excerpt.lower()
    sid = section_id.lower()
    adjust = 0.0
    if "risk_factors" in sid:
        adjust += 4.0
    if "md_and_a" in sid:
        adjust += 6.0
    if query and is_mda_query(query) and "risk_factors" in sid and "md_and_a" not in sid:
        adjust -= 8.0
    if _RISK_CROSS_REF.search(ex) and len(excerpt) < 2500:
        adjust -= 12.0
    if _OFF_TOPIC_RISK_CHUNK.search(ex):
        adjust -= 15.0
    if re.search(
        r"item\s+1a\.?\s+risk\s+factors.*material\s+adverse",
        ex,
        re.I | re.DOTALL,
    ):
        adjust += 10.0
    return adjust


def score_chunk(
    *,
    query: str,
    excerpt: str,
    label: str,
    node_source: EvidenceSourceType,
    is_xbrl_fact: bool,
    is_financial_query: bool,
    qualitative_only: bool,
    section_id: str,
    bias: SourceBias,
    anchors: list,
) -> tuple[float, dict[str, Any]]:
    """Return (total_score, component_breakdown)."""
    query_pat = concepts_for_query(query)
    components: dict[str, Any] = {}

    relevance = relevance_score(query, excerpt, label, query_pat)
    components["relevance"] = round(relevance, 3)
    components["concept_match"] = bool(query_pat and query_pat.search(excerpt))
    score = relevance

    qual_boost = qualitative_keyword_boost(query, excerpt, node_source)
    if qual_boost:
        components["qualitative_boost"] = round(qual_boost, 3)
        score += qual_boost

    if is_xbrl_fact:
        xbrl_boost = 2.0
        components["xbrl_fact_boost"] = xbrl_boost
        score += xbrl_boost
        period_align = period_alignment_score(excerpt, anchors)
        if period_align:
            components["period_alignment"] = round(period_align, 3)
            score += period_align

    if is_financial_query and is_xbrl_fact:
        components["financial_xbrl_boost"] = 3.0
        score += 3.0

    concept = label or excerpt
    if is_xbrl_fact and is_revenue_query(query) and is_revenue_concept(concept):
        components["revenue_concept_boost"] = 20.0
        score += 20.0
    if is_xbrl_fact and is_revenue_query(query) and is_securities_sales_false_positive(concept):
        components["securities_sales_penalty"] = -15.0
        score -= 15.0

    if qualitative_only and node_source == EvidenceSourceType.HTML:
        html_base = 5.0
        components["html_qualitative_base"] = html_base
        score += html_base
        if "risk_factors" in section_id:
            components["html_risk_section"] = 8.0
            score += 8.0
        if len(excerpt) > 3000:
            components["html_long_excerpt"] = 3.0
            score += 3.0

    if qualitative_only and _RISK_QUERY.search(query):
        risk_adj = risk_excerpt_score_adjustment(excerpt, section_id, query=query)
        if risk_adj:
            components["risk_excerpt_adjustment"] = round(risk_adj, 3)
            score += risk_adj

    subtotal = score
    components["subtotal_before_bias"] = round(subtotal, 3)
    multiplier = source_bias_multiplier(node_source, bias)
    components["bias_multiplier"] = multiplier
    total = subtotal * multiplier
    components["total"] = round(total, 3)
    return total, components


def rank_trace_row(
    *,
    chunk_node_id: str,
    source_type: str,
    section_id: str,
    score: float,
    components: dict[str, Any],
    excerpt_preview: str,
    structural_path: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "chunk_node_id": chunk_node_id,
        "source_type": source_type,
        "section_id": section_id,
        "score": round(score, 3),
        "components": {k: v for k, v in components.items() if k != "total"},
        "excerpt_preview": excerpt_preview,
    }
    if structural_path:
        row["structural_path_edges"] = structural_path
    return row
