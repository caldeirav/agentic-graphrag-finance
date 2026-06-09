"""Validate generated benchmark items against corpus index (011)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.bundle_version import is_v2_or_later
from evaluation.generation.comparison_gt import is_comparison_item, validate_comparison_structured
from evaluation.generation.gt_classifier import is_numeric_answer_gt
from evaluation.generation.section_paths import resolve_section_paths
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem


def load_graph_paths(index_path: Path) -> set[str]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    paths = data.get("paths", [])
    return {str(p) for p in paths}


def _validate_v2_answer_type(item: GeneratedBenchmarkItem, errors: list[str]) -> None:
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    if not answer:
        errors.append("missing_answer_gt")
        return
    answer_type = item.answer_type
    if answer_type is None:
        errors.append("missing_answer_type")
        return
    if answer_type in (AnswerType.NUMERIC, AnswerType.SHORT_LABEL):
        return
    claims = [c.strip() for c in (gt.required_claims or []) if c and c.strip()]
    if answer_type == AnswerType.NARRATIVE:
        if len(claims) < 2 or len(claims) > 8:
            errors.append("required_claims")
    elif answer_type == AnswerType.COMPARISON_STRUCTURED:
        errors.extend(validate_comparison_structured(item))
    elif not is_numeric_answer_gt(answer):
        if len(claims) < 2:
            errors.append("required_claims")


def validate_item(
    item: GeneratedBenchmarkItem,
    *,
    graph_paths: set[str],
    snapshot_accessions: set[str],
    bundle_version: str | None = None,
) -> GeneratedBenchmarkItem:
    errors: list[str] = []
    canonical_paths = list(item.expected_section_paths)
    v2 = is_v2_or_later(bundle_version or "")
    if not item.question.strip():
        errors.append("empty_question")
    bindings = item.expected_bindings.accessions
    if not bindings:
        errors.append("missing_accessions")
    elif not set(bindings).issubset(snapshot_accessions):
        errors.append("accession_not_in_snapshot")
    if item.inspiration_profile == "finagentbench" and len(bindings) < 2:
        errors.append("finagentbench_requires_multi_filing")
    if not item.expected_section_paths:
        errors.append("missing_section_paths")
    else:
        canonical_paths, unresolved = resolve_section_paths(
            item.expected_section_paths,
            graph_paths,
            snapshot_accessions=snapshot_accessions,
        )
        for path in unresolved:
            errors.append(f"unknown_section_path:{path}")
    gt = item.ground_truth
    if v2:
        _validate_v2_answer_type(item, errors)
    elif not (gt.answer or gt.rubric):
        errors.append("missing_ground_truth")
    elif item.inspiration_profile == "financebench":
        if not (gt.answer and gt.answer.strip()):
            errors.append("financebench_requires_answer")
    elif item.inspiration_profile == "finder":
        if not (gt.rubric and gt.rubric.strip()):
            errors.append("finder_requires_rubric")
    elif item.inspiration_profile == "finagentbench":
        if not ((gt.answer and gt.answer.strip()) or (gt.rubric and gt.rubric.strip())):
            errors.append("finagentbench_requires_answer_or_rubric")
    if v2 and is_comparison_item(item) and item.answer_type != AnswerType.COMPARISON_STRUCTURED:
        errors.append("invalid_answer_type")
    status = "accepted" if not errors else "rejected"
    return item.model_copy(
        update={
            "validation_status": status,
            "validation_errors": errors,
            "expected_section_paths": canonical_paths,
        }
    )
