"""Unit tests for profile-quota dev split selection (017)."""

from __future__ import annotations

from collections import Counter

import pytest

from evaluation.generation.profile_selection import (
    ProfileSelectionError,
    quota_targets,
    select_profile_balanced_items,
)
from models.benchmark_generation import GeneratedBenchmarkItem


def _item(item_id: str, profile: str) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": item_id,
            "question": f"Question for {item_id}?",
            "question_type_tag": "metrics-generated",
            "inspiration_profile": profile,
            "ground_truth": {"answer": "42"},
            "expected_bindings": {"accessions": ["0000320193-24-000123"]},
            "expected_section_paths": ["0000320193-24-000123/item_7"],
            "operation_class": "QUALITATIVE",
        }
    )


def test_quota_targets_sum_to_target() -> None:
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    targets = quota_targets(quotas, 200)
    assert sum(targets.values()) == 200
    assert targets["financebench"] == 68
    assert targets["finder"] == 66
    assert targets["finagentbench"] == 66


def test_select_profile_balanced_items_respects_quotas() -> None:
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    pool: list[GeneratedBenchmarkItem] = []
    for profile, count in [("financebench", 120), ("finder", 110), ("finagentbench", 100)]:
        for index in range(count):
            pool.append(_item(f"v2-{profile}-{index:03d}", profile))

    selected = select_profile_balanced_items(pool, quotas, 200, seed=20260602)
    counts = Counter(item.inspiration_profile for item in selected)
    assert len(selected) == 200
    assert counts["financebench"] == 68
    assert counts["finder"] == 66
    assert counts["finagentbench"] == 66


def test_select_profile_balanced_items_is_deterministic() -> None:
    quotas = {"financebench": 0.5, "finder": 0.5}
    pool = [_item(f"v2-fin-{i:03d}", "financebench" if i % 2 else "finder") for i in range(80)]
    first = select_profile_balanced_items(pool, quotas, 40, seed=7)
    second = select_profile_balanced_items(pool, quotas, 40, seed=7)
    assert [item.item_id for item in first] == [item.item_id for item in second]


def test_select_profile_balanced_items_returns_all_when_pool_small() -> None:
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    pool = [_item("v2-fin-001", "financebench"), _item("v2-finder-001", "finder")]
    selected = select_profile_balanced_items(pool, quotas, 200, seed=1)
    assert len(selected) == 2


def test_select_profile_balanced_items_raises_when_profile_short() -> None:
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    pool = [_item(f"v2-fin-{i:03d}", "financebench") for i in range(250)]
    with pytest.raises(ProfileSelectionError, match="needs 66 items but only 0"):
        select_profile_balanced_items(pool, quotas, 200, seed=1)
