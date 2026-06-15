"""Unit tests for apply_profile_balanced_dev_split (017)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evaluation.generation.bundle import apply_profile_balanced_dev_split, load_dev_split_items
from evaluation.generation.judge_generator import write_items_jsonl
from models.benchmark_generation import GeneratedBenchmarkItem


def _comparison_item(item_id: str, profile: str) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": item_id,
            "question": "Compare filings?",
            "question_type_tag": "cross-filing-comparison",
            "answer_type": "comparison_structured",
            "inspiration_profile": profile,
            "ground_truth": {
                "answer": "Both FY2025 10-K and FY2024 10-K discuss revenue in Item 7 MD&A.",
                "required_claims": [
                    "FY2025 10-K discusses revenue in Item 7 MD&A.",
                    "FY2024 10-K discusses revenue in Item 7 MD&A.",
                    "Both filings compare revenue trends in Item 7 MD&A.",
                ],
            },
            "expected_bindings": {
                "accessions": ["0000320193-25-000079", "0000320193-24-000123"],
            },
            "expected_section_paths": ["0000320193-25-000079/item_7"],
            "multi_filing_required": profile == "finagentbench",
            "operation_class": "QUALITATIVE",
            "validation_status": "accepted",
        }
    )


def test_apply_profile_balanced_dev_split_writes_dev_jsonl(tmp_path: Path) -> None:
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    pool: list[GeneratedBenchmarkItem] = []
    for profile, count in [("financebench", 120), ("finder", 110), ("finagentbench", 100)]:
        for index in range(count):
            pool.append(_comparison_item(f"v2-{profile}-{index:03d}", profile))

    write_items_jsonl(pool, tmp_path / "items" / "dev_pool.jsonl")
    report = apply_profile_balanced_dev_split(
        tmp_path,
        profile_quotas=quotas,
        target_count=200,
        seed=20260602,
    )
    selected = load_dev_split_items(tmp_path / "items" / "dev.jsonl")
    counts = Counter(item.inspiration_profile for item in selected)

    assert report["skipped"] is False
    assert report["pool_count"] == 330
    assert len(selected) == 200
    assert counts["financebench"] == 68
    assert counts["finder"] == 66
    assert counts["finagentbench"] == 66
    assert (tmp_path / "dev_selection_report.json").is_file()
    saved = json.loads((tmp_path / "dev_selection_report.json").read_text(encoding="utf-8"))
    assert saved["selected_count"] == 200
