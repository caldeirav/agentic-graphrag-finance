"""Fiscal-period temporal scope resolution and filing binding."""

from __future__ import annotations

from models.corpus import (
    CorpusTemporalScope,
    FilingBinding,
    FiscalPeriodLabel,
    infer_fiscal_year_end_month,
)
from models.filing import FilingRef
from models.graph import GraphSnapshot


def fiscal_period_label(
    filing: FilingRef,
    *,
    fiscal_year_end_month: int = 12,
) -> FiscalPeriodLabel:
    return FiscalPeriodLabel.from_filing(
        filing,
        fiscal_year_end_month=fiscal_year_end_month,
    )


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


def _match_period_label(
    refs: list[FilingRef],
    label: str,
    *,
    fiscal_year_end_month: int = 12,
) -> FilingRef | None:
    for ref in refs:
        if fiscal_period_label(ref, fiscal_year_end_month=fiscal_year_end_month).label == label:
            return ref
    return None


def resolve_temporal_scope(
    scope: CorpusTemporalScope,
    snapshot: GraphSnapshot,
) -> list[FilingRef]:
    """Resolve structured temporal scope to filing refs within snapshot."""
    fy_end = infer_fiscal_year_end_month(list(snapshot.manifest.filing_refs))
    by_form = _filings_by_form(snapshot)
    selected: list[FilingRef] = []
    notes: list[str] = []

    if scope.accessions:
        acc_set = set(scope.accessions)
        for ref in snapshot.manifest.filing_refs:
            if ref.accession in acc_set:
                selected.append(ref)
        return selected

    if scope.periods:
        for label in scope.periods:
            for refs in by_form.values():
                hit = _match_period_label(refs, label, fiscal_year_end_month=fy_end)
                if hit:
                    selected.append(hit)
                    break
        return selected

    anchor = (scope.anchor or "").strip().lower().replace("-", "_")
    if anchor in ("latest_annual", "latest_annual_report"):
        k = by_form.get("10-K", [])
        if k:
            selected.append(k[0])
        return selected

    if anchor in ("latest_quarter", "latest_q"):
        q = by_form.get("10-Q", [])
        if q:
            selected.append(q[0])
        return selected

    if anchor in ("prior_quarter", "previous_quarter"):
        q = by_form.get("10-Q", [])
        if len(q) >= 2:
            selected.append(q[1])
        elif len(q) == 1:
            notes.append("only one 10-Q in snapshot; using latest quarter")
            selected.append(q[0])
        return selected

    if scope.compare_periods:
        for label in scope.compare_periods:
            for refs in by_form.values():
                hit = _match_period_label(refs, label, fiscal_year_end_month=fy_end)
                if hit:
                    selected.append(hit)
                    break
        return selected

    return selected


def bind_filings_for_query(
    scope: CorpusTemporalScope | None,
    snapshot: GraphSnapshot,
    *,
    query: str = "",
) -> FilingBinding:
    """Bind filings for a query; uses all snapshot filings when scope empty."""
    notes: list[str] = []
    assumptions: list[str] = []

    if scope is None or (
        not scope.anchor
        and not scope.periods
        and not scope.compare_periods
        and not scope.accessions
    ):
        bound = list(snapshot.manifest.filing_refs)
        if query:
            assumptions.append("no explicit temporal scope; using full snapshot filing set")
        return FilingBinding(
            snapshot_id=snapshot.snapshot_id,
            bound_filings=bound,
            resolution_notes=notes,
            assumptions=assumptions,
        )

    bound = resolve_temporal_scope(scope, snapshot)
    if not bound and scope.anchor:
        notes.append(f"could not resolve anchor={scope.anchor} in snapshot")
    return FilingBinding(
        snapshot_id=snapshot.snapshot_id,
        bound_filings=bound,
        resolution_notes=notes,
        assumptions=assumptions,
    )
