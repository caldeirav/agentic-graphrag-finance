"""Smoke gate helpers for v1.2.0 answer-GT pool (B6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SMOKE_DIRS = (
    Path("reports/repro-v1.2-smoke"),
    Path("reports/repro-paper-v1.0-v1.2.0"),
)


def _answer_gt_item_ids(bundle_root: Path) -> list[str]:
    items_path = bundle_root / "items" / "dev.jsonl"
    ids: list[str] = []
    for line in items_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("ground_truth") or {}).get("answer"):
            ids.append(row["item_id"])
    return ids


@pytest.mark.integration
def test_v1_2_0_answer_gt_pool_size() -> None:
    bundle = Path("data/benchmarks/custom-judge/v1.2.0")
    if not bundle.is_dir():
        pytest.skip("v1.2.0 bundle not published locally")
    ids = _answer_gt_item_ids(bundle)
    assert 50 <= len(ids) <= 70


@pytest.mark.integration
@pytest.mark.parametrize("smoke_dir", SMOKE_DIRS)
def test_smoke_mrr_gate_when_report_exists(smoke_dir: Path) -> None:
    results_path = smoke_dir / "graph-full" / "results.json"
    bundle = Path("data/benchmarks/custom-judge/v1.2.0")
    if not results_path.is_file() or not bundle.is_dir():
        pytest.skip("smoke repro not run yet")
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    answer_gt = set(_answer_gt_item_ids(bundle))
    subset = [r for r in rows if r["item_id"] in answer_gt]
    if not subset:
        pytest.skip("no answer-GT rows in smoke results")
    mrr_zero = sum(1 for r in subset if (r.get("ranking_metrics") or {}).get("mrr", 0) == 0)
    assert mrr_zero <= 11, f"MRR=0 on {mrr_zero}/{len(subset)} answer-GT items (target ≤11)"
