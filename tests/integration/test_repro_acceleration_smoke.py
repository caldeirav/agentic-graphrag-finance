"""Combined 013 acceleration smoke: defer judging, per-item subgraph, resume."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evaluation.reproduction.manifest import resolve_variant_configs
from evaluation.reproduction.runner import ReproRunner
from evaluation.reproduction.snapshot_loader import load_item_subgraph
from models.reproduction import DeferJudgeConfig


@pytest.mark.integration
def test_acceleration_smoke_defer_subgraph_resume(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")

    slice_calls: list[str] = []
    real_load = load_item_subgraph

    def _track_slice(bundle_root, accessions, index, *, item_id: str):
        slice_calls.append(item_id)
        return real_load(bundle_root, accessions, index, item_id=item_id)

    audit_calls: list[int] = []

    def _track_audit(*args, **kwargs):
        audit_calls.append(1)
        from evaluation.ask_judge import run_post_query_audit as real

        return real(*args, **kwargs)

    runner = ReproRunner(
        Path("releases/paper-smoke/manifest.yaml"),
        repo_root=Path.cwd(),
        defer_config=DeferJudgeConfig(enabled=True),
    )
    graph_full = next(
        v for v in resolve_variant_configs(runner.manifest) if v.variant_id == "graph-full"
    )
    out = tmp_path / "repro-accel"

    with (
        patch("retrieval.service.run_post_query_audit", side_effect=_track_audit),
        patch(
            "evaluation.reproduction.runner.load_item_subgraph",
            side_effect=_track_slice,
        ),
    ):
        runner.run_variant(graph_full, max_items=1, output_dir=out)
        first_ids = {
            r["item_id"]
            for r in json.loads((out / "graph-full" / "results.json").read_text())
        }
        first_slice_count = len(slice_calls)
        runner.run_variant(graph_full, max_items=2, output_dir=out)

    assert len(audit_calls) == 0
    assert first_slice_count >= 1

    rows = json.loads((out / "graph-full" / "results.json").read_text(encoding="utf-8"))
    ids = [r["item_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert first_ids <= set(ids)
    assert len(ids) == 2
    assert len(slice_calls) >= 1
