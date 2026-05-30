"""Integration test for custom-judge reproduce hash (011)."""

from pathlib import Path

from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.generation.bundle import items_hash

FIXTURE = Path("tests/fixtures/custom_judge")


def test_reproduce_hash_matches_manifest():
    ds = CustomJudgeDataset(bundle_root=FIXTURE)
    manifest = ds.manifest()
    computed = items_hash(FIXTURE / "items" / "dev.jsonl")
    assert computed == manifest.items_hash
