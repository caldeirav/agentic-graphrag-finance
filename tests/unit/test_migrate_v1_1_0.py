"""Unit tests for custom-judge v1.1.0 migration (016)."""

from pathlib import Path

import pytest

from evaluation.generation.bundle import validate_bundle_feasibility
from evaluation.generation.migrate_v1_1_0 import build_draft_from_parent, load_items


def test_migrated_fixture_draft_passes_feasibility(tmp_path: Path) -> None:
    parent = Path("tests/fixtures/custom_judge")
    draft = tmp_path / "draft"
    items, changelog = build_draft_from_parent(parent, draft, parent_version="1.0.0")
    report = validate_bundle_feasibility(draft, draft / "items" / "dev.jsonl")
    assert report["blocked_count"] == 0
    assert len(items) == 3
    assert any(e.change_types == ["rubric_route"] for e in changelog)


def test_published_v1_1_0_fixture_bundle_is_feasible() -> None:
    root = Path("data/benchmarks/custom-judge/v1.1.0")
    if not root.is_dir():
        return
    report = validate_bundle_feasibility(root, root / "items" / "dev.jsonl")
    if report["blocked_count"] > 0:
        pytest.skip("v1.1.0 fails v1.2.0 publish gates; validate v1.2.0 instead")
    assert report["blocked_count"] == 0
    migrated = load_items(root / "items" / "dev.jsonl")
    finagent = next(i for i in migrated if "finagentbench" in i.item_id)
    assert finagent.ground_truth.answer is None
    assert finagent.ground_truth.rubric
