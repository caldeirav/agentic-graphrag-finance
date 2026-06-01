"""Unit tests for custom-judge relevance manifest fields (012)."""

from pathlib import Path

from evaluation.datasets.custom_judge import CustomJudgeDataset


def test_relevance_manifest_fields_optional_on_fixture() -> None:
    ds = CustomJudgeDataset(bundle_root=Path("tests/fixtures/custom_judge"))
    meta = ds.relevance_manifest()
    assert meta.labels_hash is None
    assert meta.coverage_rate is None
    assert meta.snapshot_id is None
    assert meta.labels_path is None


def test_manifest_includes_relevance_fields_when_present(tmp_path) -> None:
    import json

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "items").mkdir()
    (bundle / "items" / "dev.jsonl").write_text("", encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "dataset_name": "custom-judge",
        "version": "0.0.0-draft",
        "status": "draft",
        "item_count": 0,
        "items_hash": "sha256:" + "aa" * 32,
        "sampling_manifest_path": "sampling_manifest.json",
        "generation_config_path": "generation_config.yaml",
        "generation_judge_version": "mock",
        "evaluation_judge_version": "mock",
        "profile_counts": {},
        "corpus_bundle": {
            "snapshot_id": "s",
            "issuer_snapshots": [],
            "corpus_root": "corpus",
            "graph_node_index_path": "corpus/graph_node_index.json",
            "total_bytes": 0,
            "artifact_hashes": {},
        },
        "relevance_labels_hash": "sha256:" + "bb" * 32,
        "relevance_coverage_rate": 0.95,
        "relevance_snapshot_id": "ci-aapl-snapshot",
        "relevance_labels_path": "relevance_labels.json",
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ds = CustomJudgeDataset(bundle_root=bundle)
    meta = ds.relevance_manifest()
    assert meta.labels_hash == "sha256:" + "bb" * 32
    assert meta.coverage_rate == 0.95
    assert meta.snapshot_id == "ci-aapl-snapshot"
    assert meta.labels_path == "relevance_labels.json"
