"""Temporal scope intent for FY/quarter filing binding (021)."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from models.corpus import infer_fiscal_year_end_month
from models.enums import ComparisonMode
from models.filing import FilingRef
from models.graph import GraphSnapshot
from retrieval.macro.models import MacroBindingProposal
from retrieval.macro.pairing import annual_fiscal_year_requested, pair_period_labels
from retrieval.temporal import fiscal_period_label


class TemporalScopeIntent(BaseModel):
    anchor: str | None = None
    target_fiscal_year: int | None = None
    form_preference: str = ""
    comparison_mode: str | None = None
    period_labels: list[str] = Field(default_factory=list)
    rationale: str = ""


_QUARTER_RE = re.compile(r"\b(q[1-4]|quarter|10-q|10 q)\b", re.I)
_FY_LABEL_RE = re.compile(r"\bFY(20\d{2})\b", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _year_from_labels(labels: list[str]) -> int | None:
    for label in labels:
        m = _FY_LABEL_RE.search(label)
        if m:
            return int(m.group(1))
        if label.startswith("FY") and len(label) >= 6 and label[2:6].isdigit():
            return int(label[2:6])
    return None


def _years_in_query(query: str) -> list[int]:
    return [int(y) for y in _YEAR_RE.findall(query)]


def infer_temporal_scope_intent(
    query: str,
    *,
    temporal_anchor: str = "",
    fiscal_period_labels: list[str] | None = None,
) -> TemporalScopeIntent:
    labels = list(fiscal_period_labels or [])
    anchor = (temporal_anchor or "").strip()
    years = _years_in_query(query)
    target_year = _year_from_labels(labels) or (years[0] if len(years) == 1 else None)

    if anchor.upper().startswith("FY") and len(anchor) >= 6:
        labels = labels or [anchor.upper()]
        try:
            target_year = int(anchor[2:6])
        except ValueError:
            pass

    q = query.lower()
    comparison_mode: str | None = None
    if any(k in q for k in ("year over year", "year-over-year", "yoy", "compared to last year")):
        comparison_mode = "yoy"
    elif any(k in q for k in ("quarter over quarter", "qoq")):
        comparison_mode = "qoq"
    elif len(years) >= 2 and any(k in q for k in ("change", "from", "to", "between")):
        comparison_mode = "yoy"

    if annual_fiscal_year_requested(query) or (labels and not _QUARTER_RE.search(q)):
        fy = target_year or (years[0] if years else None)
        period = [f"FY{fy}"] if fy else labels
        return TemporalScopeIntent(
            anchor="latest_annual",
            target_fiscal_year=fy,
            form_preference="10-K",
            comparison_mode=comparison_mode,
            period_labels=period or labels,
            rationale="Annual fiscal year requested; prefer 10-K for target FY.",
        )

    if _QUARTER_RE.search(q):
        return TemporalScopeIntent(
            anchor=anchor or "latest_quarter",
            form_preference="10-Q",
            period_labels=labels,
            rationale="Quarter language detected; prefer 10-Q.",
        )

    if labels:
        return TemporalScopeIntent(
            anchor=anchor or "latest_annual",
            target_fiscal_year=target_year,
            form_preference="10-K" if not _QUARTER_RE.search(q) else "10-Q",
            period_labels=labels,
            rationale="Benchmark fiscal period labels applied.",
        )

    return TemporalScopeIntent(
        anchor=anchor or None,
        target_fiscal_year=target_year,
        comparison_mode=comparison_mode,
        rationale="No strong temporal override.",
    )


def apply_intent_to_proposal(
    proposal: MacroBindingProposal,
    intent: TemporalScopeIntent,
) -> MacroBindingProposal:
    updates: dict = {}
    if intent.period_labels:
        updates["period_labels"] = intent.period_labels
    if intent.anchor:
        updates["anchor"] = intent.anchor
    if intent.form_preference == "10-K":
        updates["quarterly_metric_cue"] = False
    if intent.comparison_mode == "yoy":
        updates["comparison_mode"] = ComparisonMode.YOY
    elif intent.comparison_mode == "qoq":
        updates["comparison_mode"] = ComparisonMode.QOQ
    if not updates:
        return proposal
    return proposal.model_copy(update=updates)


def align_filings_to_intent(
    refs: list[FilingRef],
    snapshot: GraphSnapshot,
    intent: TemporalScopeIntent,
) -> list[FilingRef]:
    if not refs:
        return refs
    manifest = list(snapshot.manifest.filing_refs or [])
    fy_end = infer_fiscal_year_end_month(manifest or refs)

    if intent.period_labels:
        label_set = set(intent.period_labels)
        matched = [
            r
            for r in refs
            if fiscal_period_label(r, fiscal_year_end_month=fy_end).label in label_set
        ]
        if intent.form_preference == "10-K":
            annual = [r for r in matched if r.form_type.upper() == "10-K"]
            if annual:
                matched = annual
        if matched:
            return matched
        broader = pair_period_labels(snapshot, intent.period_labels)
        if broader:
            if intent.form_preference == "10-K":
                annual = [r for r in broader if r.form_type.upper() == "10-K"]
                if annual:
                    return annual
            return broader

    if intent.target_fiscal_year and intent.form_preference == "10-K":
        target = intent.target_fiscal_year
        annuals = [r for r in refs if r.form_type.upper() == "10-K"]
        for ref in annuals:
            lbl = fiscal_period_label(ref, fiscal_year_end_month=fy_end).label
            if lbl == f"FY{target}":
                return [ref]
        for ref in annuals:
            if ref.period_end.year == target:
                return [ref]
        pool = [r for r in manifest if r.form_type.upper() == "10-K"]
        for ref in pool:
            lbl = fiscal_period_label(ref, fiscal_year_end_month=fy_end).label
            if lbl == f"FY{target}":
                return [ref]

    return refs


def intent_from_state(state: dict | None) -> TemporalScopeIntent | None:
    if not state:
        return None
    raw = str(state.get("temporal_scope_intent_json") or "")
    if not raw:
        return None
    try:
        return TemporalScopeIntent.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None
