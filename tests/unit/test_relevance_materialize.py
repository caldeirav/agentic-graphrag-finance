"""Unit tests for relevance materialization (012)."""

from pathlib import Path

from evaluation.reproduction.relevance import (
    compute_labels_hash,
    materialize_relevance_labels,
    resolve_item_chunk_ids,
)
from evaluation.reproduction.snapshot_loader import load_bundle_snapshot


def test_materialize_is_deterministic(tmp_path) -> None:
    src = Path("tests/fixtures/custom_judge")
    for name in ("manifest.json", "items/dev.jsonl"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    import shutil

    shutil.copytree(src / "corpus", tmp_path / "corpus", dirs_exist_ok=True)
    first = materialize_relevance_labels(tmp_path)
    second = materialize_relevance_labels(tmp_path)
    assert first.labels_hash == second.labels_hash
    assert first.coverage_rate >= 0.9


def test_labels_hash_ordering_stable() -> None:
    h1 = compute_labels_hash({"b": ["z", "a"], "a": ["c"]})
    h2 = compute_labels_hash({"a": ["c"], "b": ["a", "z"]})
    assert h1 == h2


def test_resolves_item_1a_path_with_spaces() -> None:
    draft = Path("data/benchmarks/custom-judge/drafts/live-repro-smoke")
    if not (draft / "corpus" / "graphs").is_dir():
        return
    _, snapshot = load_bundle_snapshot(draft)
    chunks, unresolved = resolve_item_chunk_ids(
        snapshot, ["0000320193-24-000123/Item 1A."]
    )
    assert not unresolved, unresolved
    assert chunks
