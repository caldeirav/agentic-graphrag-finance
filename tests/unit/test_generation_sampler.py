"""Unit tests for generation sampler (012)."""

import json
from pathlib import Path

from cli.benchmark_catalog import build_accession_catalog
from evaluation.generation.config_loader import load_allowlist, load_generation_config
from evaluation.generation.sampler import sample_issuers_and_filings, sampling_manifest_hash, write_sampling_manifest

REPO = Path(__file__).resolve().parents[2]
CI_CONFIG = REPO / "configs/benchmarks/custom_judge_ci.yaml"


def test_sampler_deterministic_hash():
    config = load_generation_config(CI_CONFIG, base=REPO)
    allowlist = load_allowlist(config.allowlist_path, base=REPO)
    catalog = build_accession_catalog(config, allowlist, repo_root=REPO, prefer_fixtures=True)
    m1 = sample_issuers_and_filings(config, allowlist, catalog)
    m2 = sample_issuers_and_filings(config, allowlist, catalog)
    assert sampling_manifest_hash(m1) == sampling_manifest_hash(m2)
    assert m1.selected_issuers[0].ticker == "AAPL"
    assert m1.selected_issuers[0].accessions


def test_write_sampling_manifest_canonical(tmp_path: Path):
    config = load_generation_config(CI_CONFIG, base=REPO)
    allowlist = load_allowlist(config.allowlist_path, base=REPO)
    catalog = build_accession_catalog(config, allowlist, repo_root=REPO, prefer_fixtures=True)
    manifest = sample_issuers_and_filings(config, allowlist, catalog)
    write_sampling_manifest(manifest, tmp_path)
    data = json.loads((tmp_path / "sampling_manifest.json").read_text())
    assert data["random_seed"] == config.random_seed
