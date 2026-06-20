"""Apply human-approved overrides to dev items in place (018)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.generation.bundle import (
    load_dev_split_items,
    validate_bundle_feasibility,
    write_scorability_report,
)
from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.annotations import load_annotation_history
from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    FailureClass,
    GeneratedBenchmarkItem,
    ItemAnnotation,
    OverrideChangelogEntry,
    ProposedOverrides,
)


def override_changelog_path(bundle_root: Path) -> Path:
    return bundle_root / "override_changelog.jsonl"


def item_content_hash(item: GeneratedBenchmarkItem) -> str:
    body = json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_regenerated_item_ids(bundle_root: Path) -> set[str]:
    """Item ids accepted via fix-boilerplate / regenerate-item (override_changelog)."""
    ids: set[str] = set()
    for entry in _load_changelog(bundle_root):
        if entry.validation_outcome != "accepted":
            continue
        if "regenerate" in (entry.rationale or "").lower():
            ids.add(entry.item_id)
    return ids


def _load_changelog(bundle_root: Path) -> list[OverrideChangelogEntry]:
    path = override_changelog_path(bundle_root)
    if not path.is_file():
        return []
    return [
        OverrideChangelogEntry.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_override_changelog(bundle_root: Path, entry: OverrideChangelogEntry) -> None:
    path = override_changelog_path(bundle_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry.model_dump_json() + "\n")


def _annotation_eligible(ann: ItemAnnotation, *, force_agent_failure: bool) -> bool:
    if ann.corpus_spot_check != CorpusSpotCheckStatus.PASSED:
        return False
    if ann.proposed_overrides is None:
        return False
    if not _proposed_overrides_nonempty(ann.proposed_overrides):
        return False
    if ann.failure_class == FailureClass.AGENT_FAILURE and not force_agent_failure:
        return False
    return True


def _proposed_overrides_nonempty(overrides: ProposedOverrides) -> bool:
    if overrides.question:
        return True
    if overrides.ground_truth is not None:
        return True
    if overrides.expected_bindings is not None:
        return True
    if overrides.expected_section_paths:
        return True
    return False


def _select_annotations(
    bundle_root: Path,
    *,
    annotation_ids: set[str] | None,
    force_agent_failure: bool,
) -> list[ItemAnnotation]:
    history = load_annotation_history(bundle_root)
    by_id = {ann.annotation_id: ann for ann in history}
    if annotation_ids:
        selected = [by_id[aid] for aid in annotation_ids if aid in by_id]
    else:
        latest: dict[str, ItemAnnotation] = {}
        for ann in history:
            prior = latest.get(ann.item_id)
            if prior is None or ann.created_at >= prior.created_at:
                latest[ann.item_id] = ann
        selected = list(latest.values())

    eligible: list[ItemAnnotation] = []
    for ann in selected:
        if not _annotation_eligible(ann, force_agent_failure=force_agent_failure):
            continue
        failed_newer = any(
            other.item_id == ann.item_id
            and other.created_at > ann.created_at
            and other.corpus_spot_check == CorpusSpotCheckStatus.FAILED
            for other in history
        )
        if failed_newer:
            continue
        eligible.append(ann)
    return eligible


def _apply_patch(item: GeneratedBenchmarkItem, overrides: ProposedOverrides) -> tuple[GeneratedBenchmarkItem, list[str]]:
    changed: list[str] = []
    updates: dict[str, object] = {}
    if overrides.question:
        updates["question"] = overrides.question
        changed.append("question")
    if overrides.expected_section_paths is not None:
        updates["expected_section_paths"] = overrides.expected_section_paths
        changed.append("expected_section_paths")
    if overrides.expected_bindings is not None:
        updates["expected_bindings"] = overrides.expected_bindings
        changed.append("expected_bindings")
    if overrides.ground_truth is not None:
        gt = item.ground_truth.model_copy(
            update={
                k: v
                for k, v in overrides.ground_truth.model_dump(exclude_unset=True).items()
                if v is not None
            }
        )
        updates["ground_truth"] = gt
        changed.append("ground_truth")
    if not updates:
        return item, changed
    return item.model_copy(update=updates), changed


def _validation_context(bundle_root: Path) -> tuple[set[str], set[str], str]:
    index_path = bundle_root / "corpus" / "graph_node_index.json"
    graph_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    snapshot_accessions: set[str] = set()
    sampling_path = bundle_root / "sampling_manifest.json"
    if sampling_path.is_file():
        data = json.loads(sampling_path.read_text(encoding="utf-8"))
        for issuer in data.get("selected_issuers", []):
            snapshot_accessions.update(issuer.get("accessions") or [])
    manifest_path = bundle_root / "manifest.json"
    bundle_version = ""
    if manifest_path.is_file():
        bundle_version = json.loads(manifest_path.read_text(encoding="utf-8")).get("version", "")
    return graph_paths, snapshot_accessions, bundle_version


def apply_overrides(
    bundle_root: Path,
    *,
    annotation_ids: set[str] | None = None,
    dry_run: bool = False,
    skip_failed: bool = False,
    force_agent_failure: bool = False,
) -> list[OverrideChangelogEntry]:
    root = resolve_draft_bundle(bundle_root)
    items_path = root / "items" / "dev.jsonl"
    items = load_dev_split_items(items_path)
    by_id = {item.item_id: item for item in items}
    annotations = _select_annotations(
        root,
        annotation_ids=annotation_ids,
        force_agent_failure=force_agent_failure,
    )
    if not annotations:
        return []

    graph_paths, snapshot_accessions, bundle_version = _validation_context(root)
    changelog: list[OverrideChangelogEntry] = []
    pending_writes: dict[str, GeneratedBenchmarkItem] = {}

    for ann in annotations:
        item = by_id.get(ann.item_id)
        if item is None:
            entry = OverrideChangelogEntry(
                item_id=ann.item_id,
                parent_item_hash="",
                reviewer_id=ann.reviewer_id,
                annotation_id=ann.annotation_id,
                changed_fields=[],
                rationale=ann.notes,
                validation_outcome="rejected",
                validation_errors=["item_not_found"],
            )
            changelog.append(entry)
            if not skip_failed:
                break
            continue

        parent_hash = item_content_hash(item)
        patched, changed_fields = _apply_patch(item, ann.proposed_overrides)  # type: ignore[arg-type]
        validated = validate_item(
            patched,
            graph_paths=graph_paths,
            snapshot_accessions=snapshot_accessions,
            bundle_version=bundle_version,
        )
        if validated.validation_status != "accepted":
            entry = OverrideChangelogEntry(
                item_id=ann.item_id,
                parent_item_hash=parent_hash,
                reviewer_id=ann.reviewer_id,
                annotation_id=ann.annotation_id,
                changed_fields=changed_fields,
                rationale=ann.notes,
                validation_outcome="rejected",
                validation_errors=list(validated.validation_errors),
            )
            changelog.append(entry)
            if not skip_failed:
                if not dry_run:
                    write_override_changelog(root, entry)
                break
            continue

        entry = OverrideChangelogEntry(
            item_id=ann.item_id,
            parent_item_hash=parent_hash,
            reviewer_id=ann.reviewer_id,
            annotation_id=ann.annotation_id,
            changed_fields=changed_fields,
            rationale=ann.notes,
            validation_outcome="accepted",
        )
        changelog.append(entry)
        pending_writes[ann.item_id] = validated
        if not dry_run:
            write_override_changelog(root, entry)

    if dry_run or not pending_writes:
        return changelog

    updated_rows = [pending_writes.get(item.item_id, item) for item in items]
    with items_path.open("w", encoding="utf-8") as handle:
        for row in updated_rows:
            handle.write(row.model_dump_json() + "\n")

    write_scorability_report(root, items_path)
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            from pydantic import ValidationError

            from models.benchmark_generation import DatasetManifest

            manifest = DatasetManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            feasibility = validate_bundle_feasibility(root, items_path, manifest=manifest)
            (root / "feasibility_report.json").write_text(
                json.dumps(feasibility, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except ValidationError:
            pass
    return changelog
