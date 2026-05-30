"""Deterministic items_hash tests (012)."""

from pathlib import Path

from evaluation.generation.bundle import items_hash

FIXTURE_ITEMS = Path("tests/fixtures/custom_judge/items/dev.jsonl")


def test_items_hash_stable():
    assert items_hash(FIXTURE_ITEMS) == items_hash(FIXTURE_ITEMS)
