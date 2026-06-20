"""Per-slot item regeneration with feedback constraints (018)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.bundle_version import is_v2_or_later
from evaluation.generation.comparison_gt import (
    format_generation_validation_feedback,
    is_boilerplate_comparison_answer,
    is_comparison_item,
)
from evaluation.generation.config_loader import load_generation_config
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.generation.judge_generator import _use_mock_judge
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.feedback import BOILERPLATE_REGEN_FEEDBACK
from evaluation.generation.review.overrides import (
    item_content_hash,
    write_fixed_items_file,
    write_override_changelog,
)
from evaluation.generation.v2_item_normalize import normalize_v2_item
from evaluation.judges.gemini_panel import JudgeParseError
from models.benchmark_generation import (
    GeneratedBenchmarkItem,
    OverrideChangelogEntry,
    SamplingManifest,
)


def _comparison_regen_context(target: GeneratedBenchmarkItem) -> str:
    bindings = ", ".join(target.expected_bindings.accessions or [])
    paths = "; ".join((target.expected_section_paths or [])[:4])
    return (
        f"Original question: {target.question}\n"
        f"Keep expected_bindings.accessions: [{bindings}]\n"
        f"Prefer expected_section_paths: [{paths}]\n"
        "Canonical answer must name both filings AND state a compared conclusion.\n"
    )


def regenerate_item(
    bundle_root: Path,
    *,
    item_id: str,
    feedback: str = "",
    repo_root: Path | None = None,
    dry_run: bool = False,
) -> GeneratedBenchmarkItem:
    root = resolve_draft_bundle(bundle_root)
    items_path = root / "items" / "dev.jsonl"
    items = load_dev_split_items(items_path)
    target = next((item for item in items if item.item_id == item_id), None)
    if target is None:
        msg = f"Item not found in dev split: {item_id}"
        raise ValueError(msg)

    config_path = root / "generation_config.yaml"
    if not config_path.is_file():
        msg = f"Missing generation_config.yaml in {root}"
        raise ValueError(msg)

    base = repo_root or Path(__file__).resolve().parents[4]
    config = load_generation_config(config_path, base=base)
    sampling_path = root / "sampling_manifest.json"
    sampling = SamplingManifest.model_validate(json.loads(sampling_path.read_text(encoding="utf-8")))

    index_path = root / "corpus" / "graph_node_index.json"
    graph_paths = sorted(load_graph_paths(index_path)) if index_path.is_file() else []
    snapshot_accessions = {
        acc for issuer in sampling.selected_issuers for acc in issuer.accessions
    }
    v2 = is_v2_or_later(config.bundle_schema_version)

    profile = target.inspiration_profile
    feedback_text = feedback.strip()
    if is_comparison_item(target):
        feedback_text = f"{_comparison_regen_context(target)}\n{feedback_text}".strip()
        answer = (target.ground_truth.answer or "").strip()
        if is_boilerplate_comparison_answer(answer) and BOILERPLATE_REGEN_FEEDBACK.strip() not in feedback_text:
            feedback_text = f"{BOILERPLATE_REGEN_FEEDBACK.strip()}\n{feedback_text}".strip()
    elif feedback_text:
        feedback_text = f"Regenerate item {item_id} preserving profile {profile}.\n{feedback_text}"
    else:
        feedback_text = f"Regenerate item {item_id} preserving profile {profile}."

    max_attempts = 1 if _use_mock_judge() else config.governance.judge_retries_per_item + 1
    validated: GeneratedBenchmarkItem | None = None
    attempt_feedback: str | None = feedback_text

    for attempt in range(max_attempts):
        try:
            if _use_mock_judge():
                regenerated = target.model_copy(
                    update={
                        "question": f"{target.question} (regenerated)",
                        "ground_truth": target.ground_truth.model_copy(
                            update={
                                "answer": (
                                    "Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K discuss "
                                    "geopolitical risk differently: Caterpillar emphasizes cyclical demand "
                                    "whereas Exxon Mobil emphasizes commodity volatility."
                                ),
                            }
                        ),
                    },
                )
            else:
                generator = GeminiItemGenerator(config, repo_root=base)
                regenerated, _ = generator.generate_one(
                    profile=profile,
                    seq=int(item_id.rsplit("-", 1)[-1]) if item_id[-1].isdigit() else 1,
                    sampling=sampling,
                    section_paths=graph_paths,
                    validation_feedback=attempt_feedback,
                )
            regenerated = regenerated.model_copy(
                update={
                    "item_id": item_id,
                    "multi_filing_required": target.multi_filing_required,
                }
            )
            if v2:
                regenerated = normalize_v2_item(regenerated)

            validated = validate_item(
                regenerated,
                graph_paths=set(graph_paths),
                snapshot_accessions=snapshot_accessions,
                bundle_version=config.bundle_schema_version,
            )
            if validated.validation_status == "accepted":
                break
            attempt_feedback = (
                f"{feedback_text}\n"
                f"{format_generation_validation_feedback(validated.validation_errors, profile=profile)}"
            )
        except (JudgeParseError, RuntimeError, ValueError, httpx.HTTPError) as exc:
            if attempt + 1 >= max_attempts:
                raise ValueError(str(exc)) from exc
            attempt_feedback = f"{feedback_text}\nParse/runtime error: {exc}"

    if validated is None or validated.validation_status != "accepted":
        errors = validated.validation_errors if validated else ["unknown"]
        msg = f"Regenerated item failed validation: {errors}"
        raise ValueError(msg)

    if dry_run:
        return validated

    parent_hash = item_content_hash(target)
    updated = [validated if row.item_id == item_id else row for row in items]
    with items_path.open("w", encoding="utf-8") as handle:
        for row in updated:
            handle.write(row.model_dump_json() + "\n")

    write_override_changelog(
        root,
        OverrideChangelogEntry(
            item_id=item_id,
            parent_item_hash=parent_hash,
            reviewer_id="regenerate-item",
            annotation_id="",
            changed_fields=["question", "ground_truth", "expected_section_paths"],
            rationale=f"regenerate: {feedback[:200]}",
            validation_outcome="accepted",
        ),
    )
    write_fixed_items_file(root)
    return validated
