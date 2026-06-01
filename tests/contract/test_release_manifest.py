"""Contract tests for release manifest schema (012)."""

from pathlib import Path

from evaluation.reproduction.manifest import load_release_manifest


def test_paper_smoke_manifest_loads() -> None:
    manifest = load_release_manifest(Path("releases/paper-smoke/manifest.yaml"))
    assert manifest.release_tag == "paper-smoke"
    assert len(manifest.variant_ids) == 5
    assert manifest.custom_judge_bundle_path == "tests/fixtures/custom_judge"


def test_fixture_repro_paper_smoke_manifest_loads() -> None:
    manifest = load_release_manifest(Path("tests/fixtures/repro/paper-smoke/manifest.yaml"))
    assert manifest.release_tag == "paper-smoke"
    assert len(manifest.variant_ids) == 5
    assert manifest.custom_judge_bundle_path == "tests/fixtures/custom_judge"


def test_paper_live_smoke_manifest_loads() -> None:
    manifest = load_release_manifest(Path("releases/paper-live-smoke/manifest.yaml"))
    assert manifest.release_tag == "paper-live-smoke"
    assert len(manifest.variant_ids) == 5
    assert "live-repro-smoke" in manifest.custom_judge_bundle_path
