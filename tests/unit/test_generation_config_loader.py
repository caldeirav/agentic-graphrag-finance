"""Unit tests for generation config loader (012)."""

from pathlib import Path

import pytest

from evaluation.generation.config_loader import (
    GenerationConfigError,
    allowlist_hash,
    compute_config_hash,
    load_generation_config,
)

REPO = Path(__file__).resolve().parents[2]
V1_CONFIG = REPO / "configs/benchmarks/custom_judge_v1.yaml"
CI_CONFIG = REPO / "configs/benchmarks/custom_judge_ci.yaml"


def test_load_v1_config_validates_quotas_and_allowlist():
    config = load_generation_config(V1_CONFIG, base=REPO)
    assert config.config_id == "custom_judge_v1"
    assert abs(sum(config.profile_quotas.values()) - 1.0) <= 0.01
    assert config.issuer_sample_count <= config.governance.max_issuers
    assert compute_config_hash(config).startswith("sha256:")


def test_allowlist_hash_stable():
    path = REPO / "configs/benchmarks/issuer_allowlist_v1.json"
    h1 = allowlist_hash(path, base=REPO)
    h2 = allowlist_hash(path, base=REPO)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_load_ci_config_for_mock_runs():
    config = load_generation_config(CI_CONFIG, base=REPO)
    assert config.config_id == "custom_judge_ci"
    assert config.governance.max_items == 3


def test_invalid_quota_sum_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
config_id: bad
random_seed: 1
allowlist_id: x
allowlist_path: configs/benchmarks/issuer_allowlist_v1.json
issuer_sample_count: 1
filing_filters:
  form_types: [10-K]
  min_fiscal_year: 2023
  max_fiscal_year: 2024
  max_filings_per_issuer: 1
profile_quotas:
  financebench: 0.5
  finder: 0.3
inspiration_profiles:
  financebench: configs/benchmarks/inspiration_profiles/financebench.yaml
generation_judge_version: mock
generation_judge_config: configs/judges/gemini_2_5_pro.yaml
evaluation_judge_version: mock
evaluation_judge_config: configs/judges/gemini_2_5_pro.yaml
governance:
  max_issuers: 1
  max_filings_per_issuer: 1
  max_items: 3
  max_judge_api_calls: 10
  max_storage_bytes: 1000
  max_wall_clock_seconds: 60
  validation_pass_rate: 0.5
  dedup_similarity_threshold: 0.85
  judge_retries_per_item: 1
output:
  drafts_root: data/benchmarks/custom-judge/drafts
  published_root: data/benchmarks/custom-judge
""",
        encoding="utf-8",
    )
    with pytest.raises(GenerationConfigError, match="profile_quotas"):
        load_generation_config(bad, base=REPO)
