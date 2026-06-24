"""Deterministic macro binding validator (008)."""

from __future__ import annotations

from models.corpus import infer_fiscal_year_end_month
from models.enums import ComparisonMode
from models.filing import FilingRef
from models.graph import GraphSnapshot
from retrieval.macro.models import (
    BindingValidationResult,
    MacroBindingProposal,
    MisalignmentCode,
    ValidationStatus,
)
from retrieval.macro.pairing import (
    detect_quarterly_metric_cue,
    materialize_proposal_filings,
    pair_period_labels,
    pair_qoq,
    pair_yoy,
)
from retrieval.skills.temporal_scope import (
    TemporalScopeIntent,
    align_filings_to_intent,
    filing_satisfies_temporal_intent,
    resolve_filings_to_intent,
)
from retrieval.temporal import fiscal_period_label


def _accession_set(refs: list[FilingRef]) -> set[str]:
    return {r.accession for r in refs}


def _comparison_mode_for(
    proposal: MacroBindingProposal,
    refs: list[FilingRef],
) -> ComparisonMode:
    if proposal.comparison_mode is not None:
        return proposal.comparison_mode
    if len(refs) >= 2:
        return ComparisonMode.YOY
    return ComparisonMode.YOY if proposal.is_comparison else ComparisonMode.YOY


def _normalize_comparison_mode(mode: ComparisonMode | None) -> ComparisonMode | None:
    if mode is None:
        return None
    return mode


def _intra_filing_yoy_xbrl(query: str, materialized: list[FilingRef]) -> bool:
    """YoY revenue-style questions can compare periods inside one 10-K XBRL fact set."""
    if len(materialized) != 1 or materialized[0].form_type != "10-K":
        return False
    q = query.lower()
    if not any(
        k in q
        for k in ("year over year", "year-over-year", "yoy", "change", "compared", "versus")
    ):
        return False
    return detect_quarterly_metric_cue(query) or any(
        k in q for k in ("revenue", "sales", "net sales", "income", "earnings")
    )


def _has_yoy_and_qoq_cues(query: str) -> bool:
    q = query.lower()
    yoy = any(k in q for k in ("year over year", "year-over-year", "yoy", "same quarter last year"))
    qoq = any(
        k in q
        for k in ("quarter over quarter", "quarter-over-quarter", "qoq", "sequential quarter")
    )
    return yoy and qoq


def _failure(
    codes: list[str],
    rationale: str,
    *,
    comparison_mode: ComparisonMode = ComparisonMode.YOY,
) -> BindingValidationResult:
    return BindingValidationResult(
        status=ValidationStatus.FAILED,
        approved_accessions=[],
        comparison_mode=comparison_mode,
        failure_codes=codes,
        rationale=rationale,
    )


def _try_narrow(
    refs: list[FilingRef],
    proposal: MacroBindingProposal,
    *,
    reason: str,
) -> BindingValidationResult | None:
    if len(refs) != 1:
        return None
    return BindingValidationResult(
        status=ValidationStatus.NARROWED,
        approved_accessions=[refs[0].accession],
        comparison_mode=ComparisonMode.YOY,
        failure_codes=[],
        rationale=(
            f"{reason} Narrowed to single anchor {refs[0].accession}; comparison intent removed."
        ),
        narrowed_from=[],
    )


def validate_macro_binding(
    proposal: MacroBindingProposal,
    snapshot: GraphSnapshot,
    *,
    cli_bound: list[FilingRef] | None = None,
    query: str = "",
    temporal_intent: TemporalScopeIntent | None = None,
) -> BindingValidationResult:
    manifest_refs = list(snapshot.manifest.filing_refs or [])
    if not manifest_refs:
        return _failure(
            [MisalignmentCode.EMPTY_CORPUS.value],
            "No filings in corpus snapshot; materialize filings before asking.",
        )

    quarterly_cue = proposal.quarterly_metric_cue or detect_quarterly_metric_cue(query)
    proposal = proposal.model_copy(update={"quarterly_metric_cue": quarterly_cue})

    if _has_yoy_and_qoq_cues(query):
        return _failure(
            [MisalignmentCode.AMBIGUOUS_COMPARISON.value],
            "Query mixes year-over-year and quarter-over-quarter cues; rephrase with one comparison intent.",
        )

    if cli_bound:
        cli_acc = _accession_set(cli_bound)
        if proposal.proposed_accessions:
            prop_acc = set(proposal.proposed_accessions)
            if prop_acc and prop_acc != cli_acc and not prop_acc.issubset(cli_acc):
                return _failure(
                    [MisalignmentCode.CLI_NL_CONFLICT.value],
                    f"CLI-bound accessions {sorted(cli_acc)} conflict with proposal {sorted(prop_acc)}.",
                )
        bound = list(cli_bound)
        narrowed_from: list[str] = []
        if temporal_intent is not None:
            bound, narrowed_from = resolve_filings_to_intent(bound, snapshot, temporal_intent)
            fy_end = infer_fiscal_year_end_month(manifest_refs)
            if temporal_intent.target_fiscal_year and temporal_intent.form_preference == "10-K":
                if not bound or not all(
                    filing_satisfies_temporal_intent(r, temporal_intent, fiscal_year_end_month=fy_end)
                    for r in bound
                ):
                    return _failure(
                        [MisalignmentCode.TEMPORAL_MISMATCH.value],
                        (
                            f"No filing in corpus satisfies calendar/FY target "
                            f"{temporal_intent.target_fiscal_year} ({', '.join(temporal_intent.period_labels)})."
                        ),
                        comparison_mode=proposal.comparison_mode or ComparisonMode.YOY,
                    )
        mode = proposal.comparison_mode or ComparisonMode.YOY
        status = ValidationStatus.NARROWED if narrowed_from else ValidationStatus.APPROVED
        return BindingValidationResult(
            status=status,
            approved_accessions=[r.accession for r in bound],
            comparison_mode=mode if len(bound) >= 2 else ComparisonMode.YOY,
            failure_codes=[],
            rationale=(
                "CLI pre-bound filing set validated against manifest."
                + (
                    f" Temporal align: {temporal_intent.rationale}"
                    if temporal_intent and temporal_intent.rationale
                    else ""
                )
                + (f" Rebound from {narrowed_from}." if narrowed_from else "")
            ),
            narrowed_from=narrowed_from,
        )

    if not proposal.intent_summary and not proposal.anchor and not proposal.proposed_accessions:
        return _failure(
            [MisalignmentCode.INVALID_PROPOSAL.value],
            "Macro planner returned an empty proposal; cannot bind filings.",
        )

    materialized = materialize_proposal_filings(proposal, snapshot, query=query)
    if materialized is None:
        mode = proposal.comparison_mode or ComparisonMode.YOY
        if proposal.is_comparison or mode in (ComparisonMode.YOY, ComparisonMode.QOQ):
            narrowed = None
            if proposal.anchor:
                from retrieval.macro.pairing import pair_single_anchor

                single = pair_single_anchor(snapshot, proposal.anchor)
                narrowed = _try_narrow(
                    single,
                    proposal,
                    reason="Comparison partner missing from corpus.",
                )
            if narrowed:
                narrowed = narrowed.model_copy(update={"comparison_mode": ComparisonMode.YOY})
                return narrowed
            code = MisalignmentCode.MISSING_COMPARISON_PARTNER.value
            if mode == ComparisonMode.QOQ:
                msg = "QoQ comparison requires at least two quarterly filings in the corpus."
            elif quarterly_cue:
                msg = (
                    "YoY quarterly comparison requires latest 10-Q and same fiscal quarter "
                    "one year earlier; materialize more history."
                )
            else:
                msg = "YoY comparison requires at least two annual filings in the corpus."
            return _failure([code], msg, comparison_mode=mode)
        return _failure(
            [MisalignmentCode.INVALID_PAIRING.value],
            "Could not resolve filing binding from macro proposal against corpus manifest.",
        )

    explicit_accessions = bool(proposal.proposed_accessions)
    if explicit_accessions:
        expected = set(proposal.proposed_accessions)
        got = _accession_set(materialized)
        if got != expected:
            return _failure(
                [MisalignmentCode.INVALID_PAIRING.value],
                f"Proposed accessions {sorted(expected)} do not match manifest pairing {sorted(got)}.",
            )

    for ref in materialized:
        if ref.accession not in {r.accession for r in manifest_refs}:
            return _failure(
                [MisalignmentCode.INVALID_ACCESSION.value],
                f"Accession {ref.accession} is not in corpus manifest.",
            )

    mode = _normalize_comparison_mode(proposal.comparison_mode)
    if mode in (ComparisonMode.YOY, ComparisonMode.QOQ, ComparisonMode.SEQUENTIAL):
        if len(materialized) < 2:
            expanded: list[FilingRef] | None = None
            if mode == ComparisonMode.YOY:
                if len(materialized) == 1 and materialized[0].form_type == "10-K":
                    expanded = pair_yoy(snapshot, quarterly_metric=False)
                if expanded is None:
                    expanded = pair_yoy(snapshot, quarterly_metric=quarterly_cue)
            elif mode in (ComparisonMode.QOQ, ComparisonMode.SEQUENTIAL):
                expanded = pair_qoq(snapshot)
            if expanded and len(expanded) >= 2:
                materialized = expanded
        if len(materialized) < 2:
            if _intra_filing_yoy_xbrl(query, materialized):
                fy_end = infer_fiscal_year_end_month(materialized)
                label = fiscal_period_label(materialized[0], fiscal_year_end_month=fy_end).label
                return BindingValidationResult(
                    status=ValidationStatus.APPROVED,
                    approved_accessions=[materialized[0].accession],
                    comparison_mode=ComparisonMode.YOY,
                    failure_codes=[],
                    rationale=(
                        f"{proposal.intent_summary or 'YoY comparison'} "
                        f"Using single 10-K {materialized[0].accession} ({label}); "
                        "compare fiscal periods via in-filing XBRL facts."
                    ),
                )
            single_narrow = _try_narrow(
                materialized,
                proposal,
                reason="Comparison requested but only one eligible filing found.",
            )
            if single_narrow:
                return single_narrow.model_copy(update={"comparison_mode": ComparisonMode.YOY})
            return _failure(
                [MisalignmentCode.MISSING_COMPARISON_PARTNER.value],
                "Comparison requires at least two filings; corpus is too sparse.",
                comparison_mode=mode,
            )
        # Planner-chosen accessions already validated above; do not re-pair with
        # quarterly_metric_cue (e.g. "net sales" + YoY may still mean annual 10-K).
        if not explicit_accessions:
            expected_pair = materialize_proposal_filings(
                proposal.model_copy(update={"proposed_accessions": []}),
                snapshot,
                query=query,
            )
            if expected_pair and _accession_set(expected_pair) != _accession_set(materialized):
                return _failure(
                    [MisalignmentCode.INVALID_PAIRING.value],
                    "Resolved filings do not match manifest pairing rules.",
                    comparison_mode=mode,
                )

    if len(materialized) == 1 and proposal.is_comparison:
        narrowed = _try_narrow(
            materialized,
            proposal,
            reason="Comparison intent could not be satisfied.",
        )
        if narrowed:
            return narrowed

    if temporal_intent is not None and materialized:
        materialized, _ = resolve_filings_to_intent(materialized, snapshot, temporal_intent)

    if len(materialized) == 1:
        cmp_mode = ComparisonMode.SEQUENTIAL
    else:
        cmp_mode = mode or ComparisonMode.YOY

    fy_end = infer_fiscal_year_end_month(materialized)
    labels = [fiscal_period_label(r, fiscal_year_end_month=fy_end).label for r in materialized]
    rationale = proposal.intent_summary or "Macro binding approved."
    if len(materialized) >= 2:
        rationale = (
            f"{rationale} Selected {len(materialized)} filings "
            f"({', '.join(labels)}) for {cmp_mode.value} comparison."
        )
    else:
        rationale = f"{rationale} Selected {materialized[0].accession} ({labels[0]})."

    return BindingValidationResult(
        status=ValidationStatus.APPROVED,
        approved_accessions=[r.accession for r in materialized],
        comparison_mode=cmp_mode,
        failure_codes=[],
        rationale=rationale,
    )
