"""Unit tests for bundle pin verification (012)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.bundle import items_hash
from evaluation.reproduction.corpus_verify import verify_bundle_pins
from evaluation.reproduction.manifest import load_release_manifest, sha256_text


def test_verify_bundle_pins_passes_on_v2_manifest() -> None:
    manifest = load_release_manifest(Path("releases/paper-v2.0/manifest.yaml"))
    result = verify_bundle_pins(manifest, repo_root=Path.cwd())
    assert result.ok, result.message


def test_verify_bundle_pins_detects_items_mismatch(tmp_path: Path) -> None:
    manifest = load_release_manifest(Path("releases/paper-v2.0/manifest.yaml"))
    bundle = tmp_path / "bundle"
    items_dir = bundle / "items"
    items_dir.mkdir(parents=True)
    dev = items_dir / "dev.jsonl"
    dev.write_text('{"item_id":"x","question":"q"}\n', encoding="utf-8")
    manifest = manifest.model_copy(
        update={
            "custom_judge_bundle_path": str(bundle.relative_to(tmp_path)),
            "items_hash": sha256_text("wrong"),
        }
    )
    result = verify_bundle_pins(manifest, repo_root=tmp_path)
    assert not result.ok
    assert any("items_hash" in line for line in result.mismatched)
