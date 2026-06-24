"""HTML/table numeric fallback when XBRL catalog is empty (022-D)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from models.query import EvidenceChunk
from retrieval.skills.numeric_computation import parse_display_value
from retrieval.skills.temporal_scope import TemporalScopeIntent
from retrieval.skills.xbrl_concept_guards import query_concept_family

_MAX_ANSWER_CHARS = 500

_ROW_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "equity": [
        re.compile(r"total\s+(?:stockholders['']?\s*)?equity", re.I),
        re.compile(r"shareholders['']?\s*equity", re.I),
        re.compile(r"stockholders['']?\s*equity", re.I),
    ],
    "cash": [
        re.compile(r"cash\s+and\s+cash\s+equivalents", re.I),
        re.compile(r"total\s+cash", re.I),
    ],
    "assets": [
        re.compile(r"^total\s+assets\b", re.I),
        re.compile(r"\btotal\s+assets\b", re.I),
    ],
}

_VALUE_CELL = re.compile(
    r"\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|trillion)?",
    re.I,
)


class HtmlTableExtraction(BaseModel):
    table_hint: str = ""
    row_label: str = ""
    column_period: str = ""
    value_display: str = ""
    chunk_id: str = ""
    confidence: str = "medium"


def _is_html_chunk(chunk: EvidenceChunk) -> bool:
    src = getattr(chunk.source_type, "value", str(chunk.source_type))
    return "HTML" in src.upper()


def _target_column_labels(temporal_intent: TemporalScopeIntent | None) -> list[str]:
    if not temporal_intent or not temporal_intent.target_fiscal_year:
        return []
    year = temporal_intent.target_fiscal_year
    return [str(year), f"FY{year}", f"Dec. 31, {year}", f"December 31, {year}"]


def _row_matches(line: str, family: str | None) -> bool:
    if not family or family not in _ROW_PATTERNS:
        return False
    return any(p.search(line) for p in _ROW_PATTERNS[family])


def _extract_value_from_line(line: str, column_labels: list[str]) -> str | None:
    if column_labels:
        for label in column_labels:
            if label not in line:
                continue
    cells = _VALUE_CELL.findall(line)
    if not cells:
        return None
    idx = 0
    if column_labels and len(cells) >= 2:
        idx = 0
    num, unit = cells[idx]
    unit = unit or ""
    display = f"${num} {unit}".strip() if unit else f"${num}"
    return display.strip()


def extract_from_html_tables(
    evidence: list[EvidenceChunk],
    query: str,
    *,
    temporal_intent: TemporalScopeIntent | None = None,
) -> HtmlTableExtraction | None:
    family = query_concept_family(query)
    if not family or family in ("tax_rate", "dividend_payout", "margin", "segment_revenue"):
        q = query.lower()
        if "equity" in q:
            family = "equity"
        elif "cash" in q:
            family = "cash"
        elif "asset" in q:
            family = "assets"
        else:
            return None

    column_labels = _target_column_labels(temporal_intent)
    for chunk in evidence:
        if not _is_html_chunk(chunk):
            continue
        lines = [ln.strip() for ln in chunk.excerpt.splitlines() if ln.strip()]
        header_idx = -1
        for i, line in enumerate(lines[:8]):
            if column_labels and any(lbl in line for lbl in column_labels):
                header_idx = i
                break
        for line in lines:
            if not _row_matches(line, family):
                continue
            value = _extract_value_from_line(line, column_labels)
            if not value:
                continue
            if parse_display_value(value) is None:
                continue
            return HtmlTableExtraction(
                table_hint=f"{family}_table",
                row_label=line[:80],
                column_period=column_labels[0] if column_labels else "",
                value_display=value,
                chunk_id=chunk.chunk_node_id,
                confidence="high" if column_labels else "medium",
            )
    return None


def html_extraction_to_payload(
    extraction: HtmlTableExtraction,
    query: str,
    metric_label: str = "",
):
    from retrieval.skills.structured_answer import StructuredAnswerPayload

    val = parse_display_value(extraction.value_display)
    if val is None:
        return None
    from retrieval.skills.numeric_computation import format_numeric_display

    rendered = format_numeric_display(val)
    if len(rendered) > _MAX_ANSWER_CHARS:
        return None
    return StructuredAnswerPayload(
        metric_label=metric_label or query[:80],
        value=rendered,
        fiscal_period=extraction.column_period,
        citation_chunk_ids=[extraction.chunk_id],
        confidence=extraction.confidence,
        abstain=False,
        metric_type="point",
        computed_value=rendered,
        inputs=[
            {
                "chunk_id": extraction.chunk_id,
                "value": extraction.value_display,
                "period_end": extraction.column_period,
            }
        ],
    )
