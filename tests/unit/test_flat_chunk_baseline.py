"""Unit tests for flat-chunk baseline (012)."""

import json
from pathlib import Path

from evaluation.reproduction.flat_chunk import _HASH_EMBED_DIM, FlatChunkBaseline
from evaluation.reproduction.manifest import load_system_variant


def test_flat_chunk_invalidates_hash_dim_cache_when_minilm_available(
    tmp_path: Path,
) -> None:
    variant = load_system_variant(Path("configs/reproduction/variants/flat-chunk.yaml"))
    bundle = Path("tests/fixtures/custom_judge")
    baseline = FlatChunkBaseline(bundle_root=bundle, variant=variant)
    cache_path = baseline._vectors_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    stale = {node_id: [0.0] * _HASH_EMBED_DIM for node_id in baseline._chunk_vectors}
    cache_path.write_text(json.dumps(stale), encoding="utf-8")

    reloaded = FlatChunkBaseline(bundle_root=bundle, variant=variant)
    if reloaded._st_model is None:
        return
    sample_dim = len(next(iter(reloaded._chunk_vectors.values())))
    assert sample_dim == reloaded._expected_embed_dim()
    assert sample_dim != _HASH_EMBED_DIM


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
