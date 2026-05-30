"""Unit tests for generation sampler (011)."""

import json
from pathlib import Path

from cli.benchmark_catalog import build_accession_catalog
from evaluation.generation.config_loader import load_allowlist, load_generation_config
from evaluation.generation.sampler import (
    SamplingError,
    sample_issuers_and_filings,
    sampling_manifest_hash,
    write_sampling_manifest,
)
from models.benchmark_generation import AccessionRecord, AllowlistEntry, IssuerAllowlist

REPO = Path(__file__).resolve().parents[2]
CI_CONFIG = REPO / "configs/benchmarks/custom_judge_ci.yaml"
V1_CONFIG = REPO / "configs/benchmarks/custom_judge_v1.yaml"


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


def test_sampler_skips_issuer_without_eligible_filings():
    config = load_generation_config(V1_CONFIG, base=REPO)
    config = config.model_copy(update={"issuer_sample_count": 2, "random_seed": 99})
    allowlist = IssuerAllowlist(
        allowlist_id="test",
        content_hash="sha256:abc",
        provenance="test",
        entries=[
            AllowlistEntry(ticker="EMPTY", sources=["test"]),
            AllowlistEntry(ticker="AAPL", sources=["test"]),
            AllowlistEntry(ticker="MSFT", sources=["test"]),
        ],
    )
    catalog = {
        "EMPTY": [
            AccessionRecord(
                accession="0000000000-00-000000",
                form_type="10-K",
                fiscal_year=2019,
                filed_at="2019-01-01",
            )
        ],
        "AAPL": [
            AccessionRecord(
                accession="0000320193-24-000123",
                form_type="10-K",
                fiscal_year=2024,
                filed_at="2024-11-01",
            )
        ],
        "MSFT": [
            AccessionRecord(
                accession="0000950170-24-087843",
                form_type="10-K",
                fiscal_year=2024,
                filed_at="2024-07-30",
            )
        ],
    }
    manifest = sample_issuers_and_filings(config, allowlist, catalog)
    assert len(manifest.selected_issuers) == 2
    tickers = {issuer.ticker for issuer in manifest.selected_issuers}
    assert tickers == {"AAPL", "MSFT"}
    assert all(issuer.accessions for issuer in manifest.selected_issuers)


def test_sampler_raises_when_insufficient_issuers_with_filings():
    config = load_generation_config(CI_CONFIG, base=REPO)
    config = config.model_copy(
        update={
            "issuer_sample_count": 5,
            "governance": config.governance.model_copy(update={"max_issuers": 5}),
        }
    )
    allowlist = IssuerAllowlist(
        allowlist_id="test",
        content_hash="sha256:abc",
        provenance="test",
        entries=[AllowlistEntry(ticker="EMPTY", sources=["test"])],
    )
    catalog = {
        "EMPTY": [
            AccessionRecord(
                accession="0000000000-00-000000",
                form_type="10-K",
                fiscal_year=2019,
                filed_at="2019-01-01",
            )
        ],
    }
    try:
        sample_issuers_and_filings(config, allowlist, catalog)
    except SamplingError as exc:
        assert "eligible filings" in str(exc)
    else:
        raise AssertionError("expected SamplingError")
