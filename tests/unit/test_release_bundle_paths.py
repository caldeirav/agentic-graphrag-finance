"""Release bundle path resolution (019)."""

from __future__ import annotations

from pathlib import Path

from evaluation.generation.review._paths import resolve_release_bundle


def test_resolve_release_bundle_falls_back_to_quality_draft(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    draft = repo / "data/benchmarks/custom-judge/drafts/quality-v2.0.1"
    (draft / "items").mkdir(parents=True)
    (draft / "items" / "dev.jsonl").write_text("{}\n", encoding="utf-8")

    resolved = resolve_release_bundle(
        repo,
        bundle_rel_path="data/benchmarks/custom-judge/v2.0.1",
        version="2.0.1",
    )
    assert resolved == draft.resolve()
