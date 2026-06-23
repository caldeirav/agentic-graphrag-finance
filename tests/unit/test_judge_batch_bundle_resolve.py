"""Judge-batch resolves unpublished paper-v1.1 bundle via quality draft."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli.commands import repro


def test_judge_batch_resolves_unpublished_bundle_via_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    published = repo / "data/benchmarks/custom-judge/v2.0.1"
    published.mkdir(parents=True)
    draft = repo / "data/benchmarks/custom-judge/drafts/quality-v2.0.1"
    (draft / "items").mkdir(parents=True)
    (draft / "items" / "dev.jsonl").write_text("{}\n", encoding="utf-8")

    rel = MagicMock(
        release_tag="paper-v1.1",
        eval_split="dev",
        custom_judge_bundle_path="data/benchmarks/custom-judge/v2.0.1",
        custom_judge_version="2.0.1",
    )
    monkeypatch.setattr(repro, "REPO_ROOT", repo)
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    monkeypatch.setattr(repro, "load_release_manifest", lambda _p: rel)

    captured: dict = {}

    def fake_batch(output_dir, **kwargs):
        captured["bundle_root"] = kwargs["bundle_root"]
        return {"judged": 0, "skipped": 0, "failed": 0}

    monkeypatch.setattr(repro, "run_judge_batch", fake_batch)
    repro.judge_batch_cmd(
        input_dir=tmp_path / "repro-out",
        manifest=tmp_path / "manifest.yaml",
        variant="graph-full",
        concurrency=2,
        max_items=None,
        force_rescore=False,
        bundle_override=None,
        item_ids_file=None,
        quiet=True,
    )
    assert captured["bundle_root"] == draft.resolve()
