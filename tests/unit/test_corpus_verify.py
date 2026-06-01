"""Unit tests for corpus verification (012)."""

from pathlib import Path

from evaluation.reproduction.corpus_verify import resolve_corpus_hashes, verify_corpus_hashes
from evaluation.reproduction.manifest import load_release_manifest


def test_verify_corpus_passes_on_fixture() -> None:
    manifest = load_release_manifest(Path("releases/paper-smoke/manifest.yaml"))
    result = verify_corpus_hashes(manifest, repo_root=Path.cwd())
    assert result.ok, result.message


def test_verify_corpus_detects_missing() -> None:
    manifest = load_release_manifest(Path("releases/paper-smoke/manifest.yaml"))
    manifest.corpus_hashes["corpus/missing.json"] = "sha256:" + "ab" * 32
    result = verify_corpus_hashes(manifest, repo_root=Path.cwd())
    assert not result.ok
    assert result.missing


def test_resolve_corpus_hashes_from_bundle_manifest(tmp_path: Path) -> None:
    import json

    bundle = tmp_path / "draft"
    bundle.mkdir()
    (bundle / "corpus").mkdir()
    index = bundle / "corpus" / "graph_node_index.json"
    index.write_text("{}", encoding="utf-8")
    from evaluation.reproduction.manifest import sha256_file

    digest = sha256_file(index)
    manifest_data = {
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
            "artifact_hashes": {"corpus/graph_node_index.json": digest},
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    release = load_release_manifest(Path("releases/paper-live-smoke/manifest.yaml"))
    resolved = resolve_corpus_hashes(release, bundle)
    assert resolved["corpus/graph_node_index.json"] == digest
