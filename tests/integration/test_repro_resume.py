"""Resume semantics for reproduction (013)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.reproduction.manifest import resolve_variant_configs
from evaluation.reproduction.runner import ReproRunner
from models.evaluation import BenchmarkResult


@pytest.mark.integration
def test_resume_skips_completed_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    runner = ReproRunner(Path("releases/paper-smoke/manifest.yaml"), repo_root=Path.cwd())
    out = tmp_path / "repro-resume"
    variant_dir = out / "graph-full"
    variant_dir.mkdir(parents=True)
    seed = [BenchmarkResult(item_id="seed-1", judge_status="ok", outcome_score=1.0)]
    (variant_dir / "results.json").write_text(
        json.dumps([r.model_dump(mode="json") for r in seed]),
        encoding="utf-8",
    )
    graph_full = next(
        v for v in resolve_variant_configs(runner.manifest) if v.variant_id == "graph-full"
    )
    runner.run_variant(graph_full, max_items=2, output_dir=out)
    rows = json.loads((variant_dir / "results.json").read_text(encoding="utf-8"))
    ids = [r["item_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert "seed-1" in ids
