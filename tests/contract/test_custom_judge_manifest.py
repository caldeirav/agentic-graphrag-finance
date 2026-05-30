"""Validate golden custom-judge manifest against Pydantic models (012)."""

import json
from pathlib import Path

from models.benchmark_generation import DatasetManifest

FIXTURE = Path("tests/fixtures/custom_judge/manifest.json")


def test_custom_judge_manifest_matches_schema():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(data)
    assert manifest.dataset_name == "custom-judge"
    assert manifest.status.value == "draft"
    assert manifest.item_count == 3
    assert manifest.corpus_bundle.graph_node_index_path == "corpus/graph_node_index.json"
