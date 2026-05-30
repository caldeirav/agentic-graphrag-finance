"""Integration smoke test for repro run-all (012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.reproduction.runner import ReproRunner


@pytest.mark.integration
def test_repro_smoke_run_all(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    runner = ReproRunner(Path("releases/paper-smoke/manifest.yaml"), repo_root=Path.cwd())
    out = tmp_path / "repro"
    repro = runner.run_all(
        output_dir=out,
        max_items=1,
        skip_relevance=True,
        strict_git=False,
    )
    assert repro.status == "completed"
    assert (out / "tables" / "headline.csv").is_file()
    assert (out / "repro_run.json").is_file()
    assert len(repro.variant_runs) == 5
