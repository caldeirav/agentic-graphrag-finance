"""Structured XBRL fact catalog for concept-aware resolution (021)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from parsing.xbrl_facts import xbrl_concept_matches_query
from retrieval.skills.temporal_scope import TemporalScopeIntent, intent_from_state


def is_xbrl_evidence_chunk(chunk: EvidenceChunk) -> bool:
    src = getattr(chunk.source_type, "value", str(chunk.source_type))
    if "XBRL" in src.upper():
        return True
    if "XBRL" in (chunk.section_id or "").upper():
        return True
    return "XBRL" in chunk.excerpt[:40].upper()

_XBRL_LINE = re.compile(
    r"XBRL (\w+):\s*(\$?[\d,.]+ (?:billion|million|trillion)?(?:\s*USD)?)"
    r"(?:\s*for period (\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2}))?",
    re.I,
)

_SEGMENT_NAMES = (
    "Energy Products",
    "Upstream",
    "Chemical Products",
    "Specialty Products",
    "machinery, energy, and transportation",
)


class XbrlFactCatalogEntry(BaseModel):
    chunk_id: str
    concept: str
    value_raw: str = ""
    value_display: str = ""
    period_start: str = ""
    period_end: str = ""
    is_annual: bool = False
    concept_family: str = ""
    segment_hint: str | None = None
    matches_query: bool = False


def _concept_family(concept: str) -> str:
    c = concept.lower()
    if "revenue" in c or "sales" in c:
        return "revenue"
    if "equity" in c:
        return "equity"
    if "asset" in c:
        return "assets"
    if "cash" in c:
        return "cash"
    if "income" in c or "earnings" in c or "eps" in c:
        return "income"
    if "liabilit" in c:
        return "liabilities"
    if "inventory" in c or "inventories" in c:
        return "inventory"
    if "tax" in c:
        return "tax"
    return "other"


def _segment_hint(excerpt: str, query: str) -> str | None:
    combined = f"{excerpt} {query}".lower()
    for name in _SEGMENT_NAMES:
        if name.lower() in combined:
            return name
    return None


def parse_xbrl_excerpt(excerpt: str) -> dict[str, str]:
    m = _XBRL_LINE.search(excerpt.strip())
    if not m:
        return {}
    start, end = m.group(3) or "", m.group(4) or ""
    is_annual = bool(start.endswith("-01-01") and end.endswith("-12-31"))
    return {
        "concept": m.group(1),
        "value_display": m.group(2).strip(),
        "value_raw": m.group(2).strip(),
        "period_start": start,
        "period_end": end,
        "is_annual": str(is_annual),
    }


def _period_matches_target(period_end: str, target_year: int | None) -> bool:
    if not target_year or not period_end:
        return True
    return str(target_year) in period_end


def build_xbrl_fact_catalog(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    state: dict | None = None,
    temporal_intent: TemporalScopeIntent | None = None,
) -> list[XbrlFactCatalogEntry]:
    intent = temporal_intent or intent_from_state(state)
    target_year = intent.target_fiscal_year if intent else None
    prefer_annual = bool(intent and intent.form_preference == "10-K")
    q_lower = query.lower()

    entries: list[XbrlFactCatalogEntry] = []
    for chunk in evidence:
        if not is_xbrl_evidence_chunk(chunk):
            continue
        parsed = parse_xbrl_excerpt(chunk.excerpt)
        if not parsed:
            continue
        concept = parsed["concept"]
        period_end = parsed.get("period_end", "")
        is_annual = parsed.get("is_annual") == "True"
        matches = xbrl_concept_matches_query(concept, query)
        if not matches and not _segment_hint(chunk.excerpt, query):
            continue
        if target_year and not _period_matches_target(period_end, target_year):
            if prefer_annual and not is_annual:
                continue
        seg = _segment_hint(chunk.excerpt, query)
        if "segment" in q_lower or "energy product" in q_lower:
            if seg and seg.lower() not in chunk.excerpt.lower() and seg.lower() not in q_lower:
                pass
        entries.append(
            XbrlFactCatalogEntry(
                chunk_id=chunk.chunk_node_id,
                concept=concept,
                value_raw=parsed.get("value_raw", ""),
                value_display=parsed.get("value_display", ""),
                period_start=parsed.get("period_start", ""),
                period_end=period_end,
                is_annual=is_annual,
                concept_family=_concept_family(concept),
                segment_hint=seg,
                matches_query=matches,
            )
        )

    if not entries:
        for chunk in evidence:
            if not is_xbrl_evidence_chunk(chunk):
                continue
            parsed = parse_xbrl_excerpt(chunk.excerpt)
            if not parsed:
                continue
            entries.append(
                XbrlFactCatalogEntry(
                    chunk_id=chunk.chunk_node_id,
                    concept=parsed["concept"],
                    value_raw=parsed.get("value_raw", ""),
                    value_display=parsed.get("value_display", ""),
                    period_start=parsed.get("period_start", ""),
                    period_end=parsed.get("period_end", ""),
                    is_annual=parsed.get("is_annual") == "True",
                    concept_family=_concept_family(parsed["concept"]),
                    segment_hint=_segment_hint(chunk.excerpt, query),
                    matches_query=xbrl_concept_matches_query(parsed["concept"], query),
                )
            )
    return entries
