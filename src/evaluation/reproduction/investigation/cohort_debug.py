"""Cohort debug re-run and replay modes (019)."""

from __future__ import annotations

from pathlib import Path

from evaluation.generation.review.queue import _load_repro_results, _outcome_score
from evaluation.reproduction.investigation._loaders import load_investigation_inputs
from evaluation.reproduction.investigation.cohort import load_tier1_cohort
from evaluation.reproduction.investigation.materialization_audit import build_materialization_audit
from evaluation.reproduction.investigation.taxonomy import (
    _synthesis_path,
    extract_weakest_judge_criterion,
    suggest_failure_class,
)
from models.evaluation import BenchmarkResult
from models.investigation import CohortDebugMode, CohortDebugSummary


def _macro_summary(result: BenchmarkResult | None) -> tuple[str, list[str], list[str]]:
    if result is None or not result.trajectory_snapshot:
        return "", [], []
    snap = result.trajectory_snapshot
    if not isinstance(snap, dict):
        return "", [], []
    plan = snap.get("macro_plan") or {}
    summary = str(plan.get("intent_summary") or plan.get("rationale") or "")
    filing_set = []
    for ref in snap.get("document_route") or []:
        if isinstance(ref, dict) and ref.get("accession"):
            filing_set.append(str(ref["accession"]))
    meso = [str(x) for x in (snap.get("meso_decisions") or [])[:10]]
    return summary, filing_set, meso


def build_cohort_debug_summary(
    *,
    item_id: str,
    result: BenchmarkResult | None,
    item,
    bundle_root: Path,
    variant_id: str,
    mode: CohortDebugMode,
    trace_event_count: int = 0,
) -> CohortDebugSummary:
    audit = (
        build_materialization_audit(bundle_root=bundle_root, item=item, result=result)
        if item is not None
        else None
    )
    suggested, _ = suggest_failure_class(
        item=item,
        result=result,
        materialization_audit=audit,
    )
    macro_summary, filing_set, meso = _macro_summary(result)
    failure_flags: list[str] = []
    if audit and audit.binding_miss:
        failure_flags.append("binding_miss")
    answer = (result.answer.text if result and result.answer else "") or ""
    if answer.startswith("Based on") and "evidence chunk" in answer.lower():
        failure_flags.append("template_dump")
    return CohortDebugSummary(
        item_id=item_id,
        variant_id=variant_id,
        mode=mode,
        macro_plan_summary=macro_summary,
        filing_set=filing_set,
        meso_decisions=meso,
        micro_evidence_count=len(result.answer.citations) if result and result.answer else 0,
        synthesis_path=_synthesis_path(result),
        citation_count=len(result.answer.citations) if result and result.answer else 0,
        outcome_score=_outcome_score(result) if result else None,
        weakest_judge_criterion=extract_weakest_judge_criterion(result),
        suggested_failure_class=suggested,
        failure_flags=failure_flags,
        trace_event_count=trace_event_count,
    )


def write_cohort_debug_summaries(
    *,
    draft: Path,
    repro_input: Path,
    cohort_path: Path,
    output_dir: Path,
    variant: str = "graph-full",
    mode: CohortDebugMode = CohortDebugMode.REPLAY,
    resume: bool = True,
) -> list[CohortDebugSummary]:
    cohort = load_tier1_cohort(cohort_path)
    inputs = load_investigation_inputs(
        draft,
        repro_input=repro_input,
        variant=variant,
        item_ids=cohort.item_ids,
    )
    results = _load_repro_results(repro_input, variant)
    debug_dir = output_dir / "cohort_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[CohortDebugSummary] = []

    for item_id in cohort.item_ids:
        summary_path = debug_dir / f"{item_id}.summary.json"
        if resume and summary_path.is_file():
            summaries.append(CohortDebugSummary.model_validate_json(summary_path.read_text()))
            continue
        item = inputs.items_by_id.get(item_id)
        result = results.get(item_id)
        summary = build_cohort_debug_summary(
            item_id=item_id,
            result=result,
            item=item,
            bundle_root=inputs.bundle_root,
            variant_id=variant,
            mode=mode,
        )
        summary_path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
        summaries.append(summary)
    return summaries


def format_progress_line(summary: CohortDebugSummary) -> str:
    outcome = summary.outcome_score if summary.outcome_score is not None else 0.0
    return (
        f"[item={summary.item_id} variant={summary.variant_id} "
        f"synthesis_path={summary.synthesis_path} citations={summary.citation_count} "
        f"outcome={outcome:.3f} weakest={summary.weakest_judge_criterion}]"
    )


def run_cohort_debug_replay(
    *,
    draft: Path,
    replay_input: Path,
    cohort_path: Path,
    output_dir: Path,
    variant: str = "graph-full",
    resume: bool = True,
    progress=None,
) -> list[CohortDebugSummary]:
    summaries = write_cohort_debug_summaries(
        draft=draft,
        repro_input=replay_input,
        cohort_path=cohort_path,
        output_dir=output_dir,
        variant=variant,
        mode=CohortDebugMode.REPLAY,
        resume=resume,
    )
    if progress:
        for summary in summaries:
            progress(format_progress_line(summary))
    return summaries
