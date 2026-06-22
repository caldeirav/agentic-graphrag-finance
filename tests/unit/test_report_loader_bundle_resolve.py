"""Report loader resolves unpublished release bundles via quality draft fallback."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction import report_loader


def test_load_item_metadata_uses_resolve_release_bundle(tmp_path: Path, monkeypatch) -> None:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    (draft / "items" / "dev.jsonl").write_text(
        json.dumps(
            {
                "item_id": "item-x",
                "question": "Q?",
                "ground_truth": {"answer": "42"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_resolve(_repo_root: Path, *, bundle_rel_path: str, version: str) -> Path:
        assert bundle_rel_path == "data/benchmarks/custom-judge/v2.0.1"
        assert version == "2.0.1"
        return draft

    monkeypatch.setattr(report_loader, "resolve_release_bundle", fake_resolve)
    meta = report_loader._load_item_metadata(
        {
            "custom_judge_bundle_path": "data/benchmarks/custom-judge/v2.0.1",
            "custom_judge_version": "2.0.1",
            "eval_split": "dev",
        },
        repo_root=tmp_path,
    )
    assert meta["item-x"]["expected_answer"] == "42"
    assert meta["item-x"]["question"] == "Q?"
