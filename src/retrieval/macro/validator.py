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
from retrieval.macro.pairing import detect_quarterly_metric_cue, materialize_proposal_filings
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
        mode = proposal.comparison_mode or ComparisonMode.YOY
        return BindingValidationResult(
            status=ValidationStatus.APPROVED,
            approved_accessions=sorted(cli_acc),
            comparison_mode=mode if len(cli_bound) >= 2 else ComparisonMode.YOY,
            failure_codes=[],
            rationale="CLI pre-bound filing set validated against manifest.",
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

    if proposal.proposed_accessions:
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
        expected_pair = materialize_proposal_filings(
            proposal.model_copy(update={"proposed_accessions": []}),
            snapshot,
            query=query,
        )
        if expected_pair and _accession_set(expected_pair) != _accession_set(materialized):
            return _failure(
                [MisalignmentCode.INVALID_PAIRING.value],
                "Explicit proposal accessions do not match manifest pairing rules.",
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
