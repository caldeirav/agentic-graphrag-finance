"""Structured XBRL fact catalog for concept-aware resolution (021/022)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from parsing.xbrl_facts import xbrl_concept_matches_query
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import (
    TemporalScopeIntent,
    intent_from_state,
    xbrl_period_matches_intent,
)
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family


def is_xbrl_evidence_chunk(chunk: EvidenceChunk) -> bool:
    src = getattr(chunk.source_type, "value", str(chunk.source_type))
    if "XBRL" in src.upper():
        return True
    if "XBRL" in (chunk.section_id or "").upper():
        return True
    return "XBRL" in chunk.excerpt[:40].upper()

_XBRL_LINE = re.compile(
    r"XBRL (\w+)(?:[^:\n]*?)?:\s*(\$?[\d,.]+ (?:billion|million|trillion)?(?:\s*USD)?)"
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
    segment_dimension: str | None = None
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


def _segment_hint(excerpt: str, query: str = "") -> str | None:
    text = excerpt.lower()
    for name in _SEGMENT_NAMES:
        if name.lower() in text:
            return name
    return None


def _segment_dimension(excerpt: str, query: str) -> str | None:
    hint = _segment_hint(excerpt, query)
    if hint:
        return hint
    m = re.search(r"segment[:\s]+([A-Za-z][A-Za-z\s&]+)", excerpt, re.I)
    if m:
        return m.group(1).strip()
    return None


def _segment_query_name(query: str) -> str | None:
    q = query.lower()
    for name in _SEGMENT_NAMES:
        if name.lower() in q:
            return name
    m = re.search(r"([\w\s&]+)\s+segment", query, re.I)
    if m:
        return m.group(1).strip()
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


def _entry_passes_filters(
    *,
    concept: str,
    excerpt: str,
    period_start: str,
    period_end: str,
    is_annual: bool,
    query: str,
    intent: TemporalScopeIntent | None,
    guard_family: str | None,
    strict_concept: bool,
) -> bool:
    seg = _segment_hint(excerpt, query)
    if strict_concept and guard_family:
        if not concept_passes_guard(concept, guard_family, segment_in_excerpt=bool(seg)):
            return False
    elif strict_concept:
        if not xbrl_concept_matches_query(concept, query) and not seg:
            return False
    if intent and not xbrl_period_matches_intent(
        period_start=period_start,
        period_end=period_end,
        is_annual=is_annual,
        intent=intent,
    ):
        return False
    return True


def build_xbrl_fact_catalog(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    state: dict | None = None,
    temporal_intent: TemporalScopeIntent | None = None,
    metric_intent: MetricIntent | None = None,
) -> list[XbrlFactCatalogEntry]:
    intent = temporal_intent or intent_from_state(state)
    guard_family = query_concept_family(query, metric_intent)
    prefer_annual = bool(intent and intent.form_preference == "10-K")

    entries: list[XbrlFactCatalogEntry] = []
    for chunk in evidence:
        if not is_xbrl_evidence_chunk(chunk):
            continue
        parsed = parse_xbrl_excerpt(chunk.excerpt)
        if not parsed:
            continue
        concept = parsed["concept"]
        period_start = parsed.get("period_start", "")
        period_end = parsed.get("period_end", "")
        is_annual = parsed.get("is_annual") == "True"
        if not _entry_passes_filters(
            concept=concept,
            excerpt=chunk.excerpt,
            period_start=period_start,
            period_end=period_end,
            is_annual=is_annual,
            query=query,
            intent=intent,
            guard_family=guard_family,
            strict_concept=True,
        ):
            continue
        if prefer_annual and intent and intent.target_fiscal_year and not is_annual:
            if period_end and str(intent.target_fiscal_year) not in period_end[:4]:
                continue
        matches = xbrl_concept_matches_query(concept, query)
        seg = _segment_hint(chunk.excerpt, query)
        seg_dim = _segment_dimension(chunk.excerpt, query)
        segment_query = _segment_query_name(query)
        if guard_family == "segment_revenue":
            if segment_query and not seg:
                continue
            if segment_query and seg and segment_query.lower() not in seg.lower():
                continue
        if guard_family == "segment_revenue" and not seg and not segment_query:
            continue
        entries.append(
            XbrlFactCatalogEntry(
                chunk_id=chunk.chunk_node_id,
                concept=concept,
                value_raw=parsed.get("value_raw", ""),
                value_display=parsed.get("value_display", ""),
                period_start=period_start,
                period_end=period_end,
                is_annual=is_annual,
                concept_family=_concept_family(concept),
                segment_hint=seg,
                segment_dimension=seg_dim,
                matches_query=matches,
            )
        )

    if not entries and guard_family:
        for chunk in evidence:
            if not is_xbrl_evidence_chunk(chunk):
                continue
            parsed = parse_xbrl_excerpt(chunk.excerpt)
            if not parsed:
                continue
            concept = parsed["concept"]
            period_start = parsed.get("period_start", "")
            period_end = parsed.get("period_end", "")
            is_annual = parsed.get("is_annual") == "True"
            if not _entry_passes_filters(
                concept=concept,
                excerpt=chunk.excerpt,
                period_start=period_start,
                period_end=period_end,
                is_annual=is_annual,
                query=query,
                intent=intent,
                guard_family=guard_family,
                strict_concept=True,
            ):
                continue
            entries.append(
                XbrlFactCatalogEntry(
                    chunk_id=chunk.chunk_node_id,
                    concept=parsed["concept"],
                    value_raw=parsed.get("value_raw", ""),
                    value_display=parsed.get("value_display", ""),
                    period_start=period_start,
                    period_end=period_end,
                    is_annual=is_annual,
                    concept_family=_concept_family(parsed["concept"]),
                    segment_hint=_segment_hint(chunk.excerpt, query),
                    segment_dimension=_segment_dimension(chunk.excerpt, query),
                    matches_query=xbrl_concept_matches_query(parsed["concept"], query),
                )
            )
    return entries
