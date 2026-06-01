"""Unit tests for flat-chunk baseline (012)."""

from pathlib import Path

from evaluation.reproduction.flat_chunk import FlatChunkBaseline
from evaluation.reproduction.manifest import load_system_variant


def test_flat_chunk_retrieves_deterministic_chunks() -> None:
    variant = load_system_variant(Path("configs/reproduction/variants/flat-chunk.yaml"))
    baseline = FlatChunkBaseline(
        bundle_root=Path("tests/fixtures/custom_judge"),
        variant=variant,
    )
    ids1 = baseline.retrieve("What was total net sales?", top_k=3)
    ids2 = baseline.retrieve("What was total net sales?", top_k=3)
    assert ids1 == ids2
    assert len(ids1) <= 3
