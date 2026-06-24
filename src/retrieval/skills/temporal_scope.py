"""Temporal scope intent for FY/quarter filing binding (021/022)."""

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
_BENCHMARK_PERIOD_RE = re.compile(r"^(20\d{2})(?:-FY|FY)?$", re.I)


def normalize_fiscal_period_labels(labels: list[str]) -> tuple[list[str], int | None]:
    """Normalize benchmark formats (2025, 2025-FY) to FY2025 labels."""
    normalized: list[str] = []
    target: int | None = None
    for label in labels:
        raw = (label or "").strip()
        if not raw:
            continue
        m = _FY_LABEL_RE.search(raw)
        if m:
            year = int(m.group(1))
            normalized.append(f"FY{year}")
            target = target or year
            continue
        m = _BENCHMARK_PERIOD_RE.match(raw)
        if m:
            year = int(m.group(1))
            normalized.append(f"FY{year}")
            target = target or year
            continue
        normalized.append(raw)
    return normalized, target


def _year_from_labels(labels: list[str]) -> int | None:
    _normalized, target = normalize_fiscal_period_labels(labels)
    if target is not None:
        return target
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
    raw_labels = list(fiscal_period_labels or [])
    labels, label_target = normalize_fiscal_period_labels(raw_labels)
    anchor = (temporal_anchor or "").strip()
    if anchor:
        norm_anchor, anchor_target = normalize_fiscal_period_labels([anchor])
        if norm_anchor:
            labels = labels or norm_anchor
            label_target = label_target or anchor_target
            anchor = norm_anchor[0]

    years = _years_in_query(query)
    target_year = label_target or _year_from_labels(labels) or (years[0] if len(years) == 1 else None)

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


def filing_satisfies_temporal_intent(
    ref: FilingRef,
    intent: TemporalScopeIntent,
    *,
    fiscal_year_end_month: int,
) -> bool:
    if not intent.target_fiscal_year:
        return True
    target = intent.target_fiscal_year
    if intent.form_preference == "10-K":
        if ref.form_type.upper() != "10-K":
            return False
        lbl = fiscal_period_label(ref, fiscal_year_end_month=fiscal_year_end_month).label
        if lbl == f"FY{target}":
            return True
        return ref.period_end.year == target
    if intent.form_preference == "10-Q":
        if ref.form_type.upper() != "10-Q":
            return False
        return str(target) in fiscal_period_label(ref, fiscal_year_end_month=fiscal_year_end_month).label
    return True


def _calendar_year_annual(manifest: list[FilingRef], target: int) -> FilingRef | None:
    candidates = [
        r for r in manifest if r.form_type.upper() == "10-K" and r.period_end.year == target
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.period_end, r.filed_at))


def _best_annual_for_intent_from_manifest(
    manifest: list[FilingRef],
    intent: TemporalScopeIntent,
    fy_end: int,
) -> FilingRef | None:
    target = intent.target_fiscal_year
    if not target:
        return None
    for ref in manifest:
        if ref.form_type.upper() != "10-K":
            continue
        lbl = fiscal_period_label(ref, fiscal_year_end_month=fy_end).label
        if lbl == f"FY{target}":
            return ref
    return _calendar_year_annual(manifest, target)


def resolve_filings_to_intent(
    refs: list[FilingRef],
    snapshot: GraphSnapshot,
    intent: TemporalScopeIntent,
) -> tuple[list[FilingRef], list[str]]:
    """Pick best filing(s) from manifest for temporal intent; return narrowed_from accessions."""
    manifest = list(snapshot.manifest.filing_refs or [])
    if not manifest:
        return refs, []
    fy_end = infer_fiscal_year_end_month(manifest)
    original_accs = [r.accession for r in refs]

    if intent.period_labels:
        label_set = set(intent.period_labels)
        matched = [
            r
            for r in manifest
            if fiscal_period_label(r, fiscal_year_end_month=fy_end).label in label_set
            and (
                not intent.form_preference
                or r.form_type.upper() == intent.form_preference.upper()
            )
        ]
        if matched:
            best = max(matched, key=lambda r: r.period_end)
            narrowed = [a for a in original_accs if a and a != best.accession]
            return [best], narrowed
        broader = pair_period_labels(snapshot, list(label_set))
        if broader:
            if intent.form_preference == "10-K":
                annual = [r for r in broader if r.form_type.upper() == "10-K"]
                if annual:
                    best = max(annual, key=lambda r: r.period_end)
                    narrowed = [a for a in original_accs if a and a != best.accession]
                    return [best], narrowed
            best = broader[0]
            narrowed = [a for a in original_accs if a and a != best.accession]
            return [best], narrowed

    if intent.target_fiscal_year and intent.form_preference == "10-K":
        best = _best_annual_for_intent_from_manifest(manifest, intent, fy_end)
        if best is not None:
            narrowed = [a for a in original_accs if a and a != best.accession]
            return [best], narrowed

    return refs, []


def align_filings_to_intent(
    refs: list[FilingRef],
    snapshot: GraphSnapshot,
    intent: TemporalScopeIntent,
) -> list[FilingRef]:
    resolved, _ = resolve_filings_to_intent(refs, snapshot, intent)
    return resolved


def xbrl_period_matches_intent(
    *,
    period_start: str,
    period_end: str,
    is_annual: bool,
    intent: TemporalScopeIntent | None,
) -> bool:
    if not intent or not intent.target_fiscal_year:
        return True
    target = intent.target_fiscal_year
    if not period_end:
        return True
    try:
        end_year = int(period_end[:4])
    except ValueError:
        return True
    start_year = end_year
    if period_start and period_start[:4].isdigit():
        start_year = int(period_start[:4])

    if intent.form_preference == "10-Q":
        return str(target) in period_end or end_year == target

    if is_annual:
        return end_year == target or start_year == target

    if start_year >= target + 1 and end_year > target:
        return False
    return end_year == target or start_year == target


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
