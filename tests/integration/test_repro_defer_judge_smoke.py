"""Deferred judging reproduction smoke (013)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from evaluation.reproduction.runner import ReproRunner


@pytest.mark.integration
def test_defer_judge_ci_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    audit_calls: list[int] = []

    def _track_audit(*args, **kwargs):
        audit_calls.append(1)
        from evaluation.ask_judge import run_post_query_audit as real

        return real(*args, **kwargs)

    runner = ReproRunner(
        Path("releases/paper-smoke/manifest.yaml"),
        repo_root=Path.cwd(),
    )
    out = tmp_path / "repro-defer"
    with patch("retrieval.service.run_post_query_audit", side_effect=_track_audit):
        runner.run_all(
            output_dir=out,
            max_items=1,
            skip_relevance=True,
            strict_git=False,
            cli_defer=True,
            resume=False,
        )
    assert len(audit_calls) == 0
    results_path = out / "graph-full" / "results.json"
    assert results_path.is_file()


@pytest.mark.integration
@pytest.mark.slow
def test_defer_judge_sc001_twenty_items(tmp_path, monkeypatch) -> None:
    """SC-001 release validation: 20 items without inline judge during generation."""
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    audit_calls: list[int] = []

    def _track_audit(*args, **kwargs):
        audit_calls.append(1)
        from evaluation.ask_judge import run_post_query_audit as real

        return real(*args, **kwargs)

    runner = ReproRunner(
        Path("releases/paper-smoke/manifest.yaml"),
        repo_root=Path.cwd(),
    )
    out = tmp_path / "repro-defer-20"
    with patch("retrieval.service.run_post_query_audit", side_effect=_track_audit):
        runner.run_all(
            output_dir=out,
            max_items=20,
            skip_relevance=True,
            strict_git=False,
            cli_defer=True,
            resume=False,
        )
    assert len(audit_calls) == 0
