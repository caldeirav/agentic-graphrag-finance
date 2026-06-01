"""Integration test: corpus rebuild verify on fixture bundle (012)."""

from pathlib import Path

import pytest

from evaluation.reproduction.corpus_verify import verify_corpus_hashes, dry_run_registry_check
from evaluation.reproduction.manifest import load_release_manifest


@pytest.mark.integration
def test_fixture_corpus_verify_after_clean_checkout_simulation() -> None:
    manifest = load_release_manifest(Path("tests/fixtures/repro/paper-smoke/manifest.yaml"))
    repo = Path.cwd()
    result = verify_corpus_hashes(manifest, repo_root=repo)
    assert result.ok, result.message
    assert not result.missing
    assert not result.mismatched
    dry_run_registry_check(manifest, repo_root=repo)


@pytest.mark.integration
def test_missing_corpus_reports_lfs_hint() -> None:
    manifest = load_release_manifest(Path("tests/fixtures/repro/paper-smoke/manifest.yaml"))
    manifest.corpus_hashes["corpus/missing-artifact.json"] = "sha256:" + "cd" * 32
    result = verify_corpus_hashes(manifest, repo_root=Path.cwd())
    assert not result.ok
    assert result.missing
    assert any("git lfs pull" in hint for hint in result.lfs_hints)
    assert "git lfs pull" in result.message
