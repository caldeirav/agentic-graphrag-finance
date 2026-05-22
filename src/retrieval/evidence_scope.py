"""Scope evidence to bound filings and anchor period-of-report."""

from __future__ import annotations

import calendar
import re
from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk

_PERIOD_CLAUSE = re.compile(r"for period\s+(.+)", re.I)
_ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_US_DATE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
)

_PERIOD_TOLERANCE_DAYS = 7
_PERIOD_MISMATCH_DAYS = 90


def document_id_for_accession(accession: str) -> str:
    return f"doc-{accession}"


def allowed_document_ids(filings: list[FilingRef]) -> set[str]:
    return {document_id_for_accession(f.accession) for f in filings}


def node_in_allowed_documents(node_id: str, doc_ids: set[str]) -> bool:
    if not doc_ids:
        return True
    return any(node_id == doc_id or node_id.startswith(f"{doc_id}-") for doc_id in doc_ids)


def anchor_period_ends(filings: list[FilingRef]) -> list[date]:
    return [f.period_end for f in filings if f.period_end]


def _parse_us_date(text: str) -> date | None:
    m = _US_DATE.search(text.strip())
    if not m:
        return None
    month_name, day, year = m.group(1), int(m.group(2)), int(m.group(3))
    month = 0
    for i in range(1, 13):
        if month_name.lower() == calendar.month_name[i].lower():
            month = i
            break
        if month_name.lower() == calendar.month_abbr[i].lower():
            month = i
            break
    if not month:
        return None
    return date(year, month, day)


def _parse_iso_date(text: str) -> date | None:
    m = _ISO_DATE.search(text.strip())
    if not m:
        return None
    return date.fromisoformat(m.group(1))


def parse_period_range_from_excerpt(excerpt: str) -> tuple[date | None, date | None]:
    """Parse XBRL duration or instant period from a graph evidence excerpt."""
    m = _PERIOD_CLAUSE.search(excerpt)
    if not m:
        return None, None
    clause = m.group(1).strip().rstrip(".")
    if re.search(r"\s+to\s+", clause, re.I):
        parts = re.split(r"\s+to\s+", clause, maxsplit=1, flags=re.I)
        start = _parse_iso_date(parts[0]) or _parse_us_date(parts[0])
        end = _parse_iso_date(parts[1]) or _parse_us_date(parts[1])
        return start, end
    if " - " in clause:
        left, right = clause.split(" - ", maxsplit=1)
        start = _parse_iso_date(left) or _parse_us_date(left)
        end = _parse_iso_date(right) or _parse_us_date(right)
        return start, end
    single = _parse_iso_date(clause) or _parse_us_date(clause)
    return single, single


def parse_period_end_from_excerpt(excerpt: str) -> date | None:
    """Parse period end (duration end or instant) from excerpt."""
    _start, end = parse_period_range_from_excerpt(excerpt)
    return end


def period_matches_anchor(
    fact_period_end: date | None,
    anchors: list[date],
    *,
    excerpt: str | None = None,
    tolerance_days: int = _PERIOD_TOLERANCE_DAYS,
) -> bool:
    if not anchors:
        return True
    if excerpt:
        start, end = parse_period_range_from_excerpt(excerpt)
        if start and end and start != end:
            for anchor in anchors:
                if start <= anchor <= end:
                    return True
                if abs((end - anchor).days) <= tolerance_days:
                    return True
    if fact_period_end is None:
        return True
    for anchor in anchors:
        if abs((fact_period_end - anchor).days) <= tolerance_days:
            return True
    return False


def period_alignment_score(
    excerpt: str,
    anchors: list[date],
    *,
    tolerance_days: int = _PERIOD_TOLERANCE_DAYS,
    mismatch_days: int = _PERIOD_MISMATCH_DAYS,
) -> float:
    """Score boost/penalty for XBRL period alignment with bound filing period_end."""
    if not anchors:
        return 0.0
    if period_matches_anchor(
        parse_period_end_from_excerpt(excerpt),
        anchors,
        excerpt=excerpt,
        tolerance_days=tolerance_days,
    ):
        return 8.0
    fact_end = parse_period_end_from_excerpt(excerpt)
    if fact_end is None:
        return 0.0
    closest = min(abs((fact_end - anchor).days) for anchor in anchors)
    if closest > mismatch_days:
        return -15.0
    return -3.0


def filter_evidence_for_filing_set(
    evidence: list[EvidenceChunk],
    filings: list[FilingRef],
) -> list[EvidenceChunk]:
    """Keep bound-filing evidence; prefer facts whose period matches period_end."""
    if not filings:
        return evidence
    doc_ids = allowed_document_ids(filings)
    scoped = [c for c in evidence if node_in_allowed_documents(c.chunk_node_id, doc_ids)]
    if not scoped:
        return []

    html_chunks = [
        c
        for c in scoped
        if c.source_type == EvidenceSourceType.HTML
        or getattr(c.source_type, "value", "") == EvidenceSourceType.HTML.value
    ]
    numeric_chunks = [c for c in scoped if c not in html_chunks]

    anchors = anchor_period_ends(filings)
    aligned_numeric = [
        c
        for c in numeric_chunks
        if period_matches_anchor(
            parse_period_end_from_excerpt(c.excerpt),
            anchors,
            excerpt=c.excerpt,
        )
    ]
    if not aligned_numeric:
        aligned_numeric = numeric_chunks

    if html_chunks:
        return html_chunks + aligned_numeric
    return aligned_numeric
