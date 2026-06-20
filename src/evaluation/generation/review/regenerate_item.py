"""Per-slot item regeneration with feedback constraints (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.generation.judge_generator import _use_mock_judge
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.overrides import item_content_hash, write_override_changelog
from models.benchmark_generation import GeneratedBenchmarkItem, OverrideChangelogEntry, SamplingManifest


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

    import yaml

    from evaluation.generation.config_loader import load_generation_config

    base = repo_root or Path(__file__).resolve().parents[4]
    config = load_generation_config(config_path, base=base)
    sampling_path = root / "sampling_manifest.json"
    sampling = SamplingManifest.model_validate(json.loads(sampling_path.read_text(encoding="utf-8")))

    index_path = root / "corpus" / "graph_node_index.json"
    graph_paths = sorted(load_graph_paths(index_path)) if index_path.is_file() else []
    snapshot_accessions = {
        acc for issuer in sampling.selected_issuers for acc in issuer.accessions
    }

    profile = target.inspiration_profile
    feedback_text = feedback.strip()
    if feedback_text:
        feedback_text = f"Regenerate item {item_id} preserving profile {profile}.\n{feedback_text}"

    if _use_mock_judge():
        regenerated = target.model_copy(
            update={"question": f"{target.question} (regenerated)"},
        )
    else:
        generator = GeminiItemGenerator(config, repo_root=base)
        regenerated, _ = generator.generate_one(
            profile=profile,
            seq=int(item_id.rsplit("-", 1)[-1]) if item_id[-1].isdigit() else 1,
            sampling=sampling,
            section_paths=graph_paths,
            validation_feedback=feedback_text or None,
        )
        regenerated = regenerated.model_copy(update={"item_id": item_id})

    validated = validate_item(
        regenerated,
        graph_paths=set(graph_paths),
        snapshot_accessions=snapshot_accessions,
        bundle_version=config.bundle_schema_version,
    )
    if validated.validation_status != "accepted":
        msg = f"Regenerated item failed validation: {validated.validation_errors}"
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
    return validated
