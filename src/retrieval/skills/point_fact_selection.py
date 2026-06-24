"""Primary annual point-fact selection from XBRL catalog (022-B)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent, xbrl_period_matches_intent
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry

_CASH_PREFERRED = re.compile(r"^CashAndCashEquivalents(?:AtCarryingValue)?$", re.I)
_ASSETS_EXACT = re.compile(r"^Assets$", re.I)
_EQUITY_RANK = (
    re.compile(r"StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", re.I),
    re.compile(r"StockholdersEquityIncluding", re.I),
    re.compile(r"StockholdersEquity$", re.I),
)


class PointFactSelection(BaseModel):
    concept: str
    period_end: str = ""
    value_normalized: float | None = None
    value_display: str = ""
    scale: str = "units"
    issuer_ticker: str = ""
    accession: str = ""
    chunk_id: str = ""
    confidence: str = "high"


def _chunk_accession_map(
    evidence: list[EvidenceChunk],
    filing_set: list[FilingRef],
) -> dict[str, str]:
    default_acc = filing_set[0].accession if filing_set else ""
    out: dict[str, str] = {}
    for chunk in evidence:
        acc = (chunk.accession or "").strip() or default_acc
        out[chunk.chunk_node_id] = acc
    return out


def _ticker_for_accession(accession: str, filing_set: list[FilingRef]) -> str:
    for ref in filing_set:
        if ref.accession == accession:
            return getattr(ref, "ticker", "") or ref.cik
    return ""


def _equity_rank(concept: str) -> int:
    for idx, pat in enumerate(_EQUITY_RANK):
        if pat.search(concept):
            return idx
    if "StockholdersEquity" in concept and "Other" not in concept:
        return len(_EQUITY_RANK)
    return 99


def _concept_rank(concept: str, family: str | None) -> int:
    if family == "equity":
        return _equity_rank(concept)
    if family == "cash":
        return 0 if _CASH_PREFERRED.search(concept) else 5
    if family == "assets":
        if _ASSETS_EXACT.search(concept):
            return 0
        if re.search(r"AssetsCurrent|AssetsNoncurrent", concept, re.I):
            return 3
        return 8
    return 10


def _detect_scale(value_display: str) -> str:
    raw = value_display.lower()
    if "billion" in raw:
        return "billions"
    if "million" in raw:
        return "millions"
    if "thousand" in raw:
        return "thousands"
    return "units"


def select_point_fact(
    catalog: list[XbrlFactCatalogEntry],
    query: str,
    metric_intent: MetricIntent,
    *,
    temporal_intent: TemporalScopeIntent | None = None,
    evidence: list[EvidenceChunk] | None = None,
    filing_set: list[FilingRef] | None = None,
) -> PointFactSelection | None:
    if metric_intent.metric_type != "point":
        return None
    family = query_concept_family(query, metric_intent)
    if not family and "cash" in query.lower():
        family = "cash"
    if not family and "asset" in query.lower():
        family = "assets"

    acc_map = _chunk_accession_map(evidence or [], filing_set or [])
    allowed_accessions = {f.accession for f in (filing_set or []) if f.accession}

    scored: list[tuple[float, XbrlFactCatalogEntry, str]] = []
    for entry in catalog:
        if family and not concept_passes_guard(
            entry.concept,
            family,
            segment_in_excerpt=bool(entry.segment_hint),
        ):
            continue
        if temporal_intent and not xbrl_period_matches_intent(
            period_start=entry.period_start,
            period_end=entry.period_end,
            is_annual=entry.is_annual,
            intent=temporal_intent,
        ):
            continue
        accession = acc_map.get(entry.chunk_id, "")
        if allowed_accessions and accession and accession not in allowed_accessions:
            continue
        rank = _concept_rank(entry.concept, family)
        score = 100.0 - rank
        if entry.is_annual:
            score += 20.0
        if entry.matches_query:
            score += 10.0
        if temporal_intent and temporal_intent.target_fiscal_year:
            if str(temporal_intent.target_fiscal_year) in entry.period_end:
                score += 15.0
        scored.append((score, entry, accession))

    if not scored:
        return None

    scored.sort(key=lambda t: t[0], reverse=True)
    _, best, accession = scored[0]
    from retrieval.skills.numeric_computation import parse_display_value

    val = parse_display_value(best.value_display)
    ticker = _ticker_for_accession(accession, filing_set or [])
    confidence = "high" if best.is_annual and (family != "equity" or _equity_rank(best.concept) < 5) else "medium"
    return PointFactSelection(
        concept=best.concept,
        period_end=best.period_end,
        value_normalized=val,
        value_display=best.value_display,
        scale=_detect_scale(best.value_display),
        issuer_ticker=ticker,
        accession=accession,
        chunk_id=best.chunk_id,
        confidence=confidence,
    )
