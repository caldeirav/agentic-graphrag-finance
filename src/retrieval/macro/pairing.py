"""YoY/QoQ pairing and quarterly-metric cue detection (008)."""

from __future__ import annotations

from pathlib import Path

import yaml

from models.corpus import CorpusTemporalScope, infer_fiscal_year_end_month
from models.enums import ComparisonMode
from models.filing import FilingRef
from models.graph import GraphSnapshot
from retrieval.macro.models import MacroBindingProposal
from retrieval.temporal import fiscal_period_label, resolve_temporal_scope

_PHRASES_CACHE: dict | None = None


def _load_phrases() -> dict:
    global _PHRASES_CACHE
    if _PHRASES_CACHE is not None:
        return _PHRASES_CACHE
    path = Path("configs/macro_phrases.yaml")
    if path.exists():
        _PHRASES_CACHE = yaml.safe_load(path.read_text()) or {}
    else:
        _PHRASES_CACHE = {}
    return _PHRASES_CACHE


def infer_anchor_from_query(query: str) -> str | None:
    """Infer temporal anchor from NL when the macro planner omits anchor."""
    q = query.lower()
    if any(k in q for k in ("quarter over quarter", "qoq", "sequential quarter")):
        return None
    quarterly_cues = (
        "prior quarter",
        "previous quarter",
        "latest quarter",
        "this quarter",
        "most recent quarter",
        "most recent quarterly",
        "quarterly filing",
        "recent 10-q",
        "recent 10 q",
        "10-q",
        "10 q",
    )
    if any(k in q for k in quarterly_cues):
        if "prior quarter" in q or "previous quarter" in q:
            return "prior_quarter"
        return "latest_quarter"
    if any(k in q for k in ("annual report", "latest 10-k", "10-k", "10k", "fiscal year")):
        if not any(k in q for k in ("quarter", "10-q", "10 q")):
            return "latest_annual"
    if "risk factor" in q and "quarter" not in q:
        return "latest_annual"
    return None


def infer_form_type_preference(query: str) -> str | None:
    """Prefer 10-Q vs 10-K when the question names a form type explicitly."""
    q = query.lower()
    if any(k in q for k in ("10-q", "10 q", "quarterly filing", "quarterly report")):
        return "10-Q"
    if any(k in q for k in ("10-k", "10 k", "annual report")) and "quarter" not in q:
        return "10-K"
    return None


def detect_quarterly_metric_cue(query: str) -> bool:
    q = query.lower()
    tokens = _load_phrases().get("quarterly_metric_tokens") or [
        "revenue",
        "sales",
        "net income",
        "earnings",
    ]
    return any(token in q for token in tokens)


def _filings_by_form(snapshot: GraphSnapshot) -> dict[str, list[FilingRef]]:
    refs = list(snapshot.manifest.filing_refs)
    by_form: dict[str, list[FilingRef]] = {}
    for ref in refs:
        by_form.setdefault(ref.form_type, []).append(ref)
    for form in by_form:
        by_form[form] = sorted(
            by_form[form],
            key=lambda r: (r.period_end, r.filed_at),
            reverse=True,
        )
    return by_form


def _prior_year_label(label: str) -> str:
    if label.startswith("FY") and "-Q" in label:
        year_part, rest = label.split("-", 1)
        year = int(year_part[2:])
        return f"FY{year - 1}-{rest}"
    if label.startswith("FY") and label[2:].isdigit():
        return f"FY{int(label[2:]) - 1}"
    return label


def pair_yoy(snapshot: GraphSnapshot, *, quarterly_metric: bool) -> list[FilingRef] | None:
    by_form = _filings_by_form(snapshot)
    if quarterly_metric:
        quarters = by_form.get("10-Q", [])
        if not quarters:
            return None
        latest = quarters[0]
        fy_end = infer_fiscal_year_end_month(quarters)
        latest_label = fiscal_period_label(latest, fiscal_year_end_month=fy_end).label
        target = _prior_year_label(latest_label)
        partner = next(
            (
                q
                for q in quarters
                if fiscal_period_label(q, fiscal_year_end_month=fy_end).label == target
            ),
            None,
        )
        if partner is None:
            return None
        return [latest, partner]

    annuals = by_form.get("10-K", [])
    if len(annuals) < 2:
        return None
    return [annuals[0], annuals[1]]


def pair_qoq(snapshot: GraphSnapshot) -> list[FilingRef] | None:
    quarters = _filings_by_form(snapshot).get("10-Q", [])
    if len(quarters) < 2:
        return None
    return [quarters[0], quarters[1]]


def pair_single_anchor(snapshot: GraphSnapshot, anchor: str) -> list[FilingRef]:
    scope = CorpusTemporalScope(anchor=anchor)
    return resolve_temporal_scope(scope, snapshot)


def pair_period_labels(snapshot: GraphSnapshot, labels: list[str]) -> list[FilingRef]:
    scope = CorpusTemporalScope(periods=labels)
    return resolve_temporal_scope(scope, snapshot)


def materialize_proposal_filings(
    proposal: MacroBindingProposal,
    snapshot: GraphSnapshot,
    *,
    query: str = "",
) -> list[FilingRef] | None:
    """Resolve proposal hints to concrete filing refs; None if pairing cannot be satisfied."""
    if not snapshot.manifest.filing_refs:
        return None

    if proposal.proposed_accessions:
        acc_set = set(proposal.proposed_accessions)
        refs = [r for r in snapshot.manifest.filing_refs if r.accession in acc_set]
        if len(refs) != len(acc_set):
            return None
        form_pref = infer_form_type_preference(query)
        if form_pref and len(refs) == 1 and refs[0].form_type != form_pref:
            by_form = _filings_by_form(snapshot).get(form_pref, [])
            anchor = proposal.anchor or infer_anchor_from_query(query)
            if anchor and by_form:
                anchored = pair_single_anchor(snapshot, anchor)
                anchored = [r for r in anchored if r.form_type == form_pref]
                if anchored:
                    return anchored
            if by_form:
                return [by_form[0]]
        return refs

    mode = proposal.comparison_mode
    quarterly = proposal.quarterly_metric_cue or detect_quarterly_metric_cue(query)

    inferred_anchor = infer_anchor_from_query(query)
    if (
        not proposal.is_comparison
        and mode in (None, ComparisonMode.YOY)
        and inferred_anchor
        and not proposal.period_labels
    ):
        refs = pair_single_anchor(snapshot, inferred_anchor)
        if refs:
            form_pref = infer_form_type_preference(query)
            if form_pref:
                filtered = [r for r in refs if r.form_type == form_pref]
                if filtered:
                    return filtered
            return refs

    if mode == ComparisonMode.YOY or (
        proposal.is_comparison and mode in (None, ComparisonMode.YOY)
    ):
        return pair_yoy(snapshot, quarterly_metric=quarterly)

    if mode == ComparisonMode.QOQ:
        return pair_qoq(snapshot)

    if mode == ComparisonMode.SEQUENTIAL:
        return pair_qoq(snapshot)

    if proposal.period_labels:
        refs = pair_period_labels(snapshot, proposal.period_labels)
        return refs or None

    if proposal.anchor:
        refs = pair_single_anchor(snapshot, proposal.anchor)
        return refs or None

    # Narrative / annual default when query mentions risk or annual report
    q = query.lower()
    if any(k in q for k in ("risk factor", "annual report", "10-k", "10k")):
        refs = pair_single_anchor(snapshot, "latest_annual")
        return refs or None

    if "prior quarter" in q or "previous quarter" in q:
        refs = pair_single_anchor(snapshot, "prior_quarter")
        return refs or None

    if "latest quarter" in q or "this quarter" in q:
        refs = pair_single_anchor(snapshot, "latest_quarter")
        return refs or None

    if quarterly and not proposal.is_comparison:
        refs = pair_single_anchor(snapshot, "latest_quarter")
        return refs or None

    return None
