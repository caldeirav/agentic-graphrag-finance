"""Integration test: repro workflow makes no EDGAR network calls (012)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from evaluation.reproduction.runner import ReproRunner


@pytest.mark.integration
def test_repro_run_all_blocks_edgar_network(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")

    def forbidden(*args, **kwargs):
        raise AssertionError("EDGAR network call attempted during offline repro")

    import httpx

    monkeypatch.setattr(httpx, "Client", forbidden)

    import ingestion.edgar_client as edgar_mod

    monkeypatch.setattr(edgar_mod, "httpx", MagicMock(Client=forbidden))

    runner = ReproRunner(
        Path("tests/fixtures/repro/paper-smoke/manifest.yaml"),
        repo_root=Path.cwd(),
    )
    repro = runner.run_all(
        output_dir=tmp_path / "repro",
        max_items=1,
        skip_relevance=True,
        strict_git=False,
    )
    assert repro.status == "completed"
