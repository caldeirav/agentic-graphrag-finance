"""Heuristic section scoring for meso router (with trace components)."""

from __future__ import annotations

import re
from typing import Any

_MDA_QUERY = re.compile(
    r"\b(md&a|mda|management['\u2019]s discussion|management discussion|"
    r"managements discussion)\b",
    re.I,
)
_RISK_QUERY = re.compile(r"\b(risk|factor|factors|item\s*1a)\b", re.I)


def is_mda_query(query: str) -> bool:
    return bool(_MDA_QUERY.search(query))


def is_risk_only_query(query: str) -> bool:
    return bool(_RISK_QUERY.search(query)) and not is_mda_query(query)


def score_section(
    *,
    label: str,
    node_id: str,
    section_id: str,
    query: str,
    prefer_html: bool,
    filing_accessions: list[str],
) -> tuple[float, dict[str, float]]:
    """Return (total_score, component_breakdown)."""
    q = query.lower()
    label_lower = label.lower()
    section_id_lower = section_id.lower()
    components: dict[str, float] = {}

    base = 1.0 if any(k in label_lower for k in q.split()[:5]) else 0.3
    components["keyword_match"] = base
    score = base

    if any(
        k in label_lower
        for k in ("financial", "balance", "income", "cash", "liquidity", "margin")
    ):
        components["financial_label"] = 0.4
        score += 0.4

    if any(k in q for k in ("revenue", "sales", "driver", "segment", "growth")):
        if any(
            k in label_lower
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
            components["revenue_query_section"] = 0.5
            score += 0.5

    if "xbrl" in label_lower and any(
        k in q for k in ("revenue", "sales", "income", "assets", "cash", "earnings")
    ):
        components["xbrl_numeric_query"] = 2.0
        score += 2.0

    if prefer_html and ("xbrl-facts" in node_id or "xbrl facts" in label_lower):
        if is_mda_query(q) or any(
            k in q for k in ("risk", "management", "discussion", "policy", "footnote")
        ):
            components["xbrl_bucket_penalty"] = -4.0
            score -= 4.0

    if prefer_html and ("html-" in node_id or section_id_lower.startswith("html")):
        components["html_preference"] = 2.5
        score += 2.5

    if prefer_html and is_mda_query(q):
        if "md_and_a" in section_id_lower or "html-md" in node_id:
            components["mda_section_boost"] = 15.0
            score += 15.0
        if any(
            k in label_lower
            for k in ("management", "discussion", "analysis", "md&a", "mda")
        ):
            components["mda_label_boost"] = 8.0
            score += 8.0
        if "risk_factors" in section_id_lower or "html-risk" in node_id:
            components["mda_query_risk_item_penalty"] = -4.0
            score -= 4.0
    elif prefer_html and is_risk_only_query(q):
        if "risk_factors" in section_id_lower or "html-risk" in node_id:
            components["risk_section_boost"] = 12.0
            score += 12.0
    elif prefer_html and _RISK_QUERY.search(q):
        if any(
            k in label_lower or section_id_lower
            for k in ("risk", "1a", "html-risk", "risk_factors")
        ):
            components["risk_keyword"] = 3.0
            score += 3.0

    if prefer_html and not is_mda_query(q) and any(
        k in label_lower for k in ("risk", "management", "md&a", "business", "item 7")
    ):
        components["html_narrative_label"] = 0.8
        score += 0.8

    if prefer_html and any(acc in node_id for acc in filing_accessions):
        components["bound_filing_10k"] = 1.0
        score += 1.0

    components["total"] = round(score, 3)
    return score, components


def section_trace_row(
    *,
    section_node_id: str,
    label: str,
    section_id: str,
    score: float,
    components: dict[str, float],
    path: list[str],
) -> dict[str, Any]:
    return {
        "section_node_id": section_node_id,
        "label": label[:120],
        "section_id": section_id,
        "score": round(score, 3),
        "components": {k: v for k, v in components.items() if k != "total"},
        "path": path[:3],
    }
