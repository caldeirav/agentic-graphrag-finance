"""Integration smoke gate for paper-v2.0 agent iteration."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.reproduction.smoke_gate import (
    SmokeGateThresholds,
    evaluate_smoke_gate,
    load_smoke_item_ids,
    profile_map_from_bundle,
)

SMOKE_DIRS = (
    Path("reports/repro-paper-v1.0-smoke"),
    Path("reports/smoke-v2-agent"),
)


@pytest.mark.integration
def test_v2_smoke_item_list_present() -> None:
    bundle = Path("data/benchmarks/custom-judge/v2.0.0")
    if not bundle.is_dir():
        pytest.skip("v2.0.0 bundle not present locally")
    ids = load_smoke_item_ids(bundle)
    assert 40 <= len(ids) <= 60


@pytest.mark.integration
@pytest.mark.parametrize("smoke_dir", SMOKE_DIRS)
def test_v2_smoke_gate_when_report_exists(smoke_dir: Path) -> None:
    results_path = smoke_dir / "graph-full" / "results.json"
    bundle = Path("data/benchmarks/custom-judge/v2.0.0")
    if not results_path.is_file() or not bundle.is_dir():
        pytest.skip("smoke repro not run yet")
    item_ids = load_smoke_item_ids(bundle)
    profiles = profile_map_from_bundle(bundle)
    result = evaluate_smoke_gate(
        results_path,
        item_ids,
        thresholds=SmokeGateThresholds(min_task_success=0.25),
        profile_by_item=profiles,
    )
    if not result.ok:
        pytest.fail("\n".join(result.failures))
