# Generation Config Schema Contract (012)

**Default file**: `configs/benchmarks/custom_judge_v1.yaml`

## YAML schema (illustrative)

```yaml
config_id: custom_judge_v1
random_seed: 42

allowlist_id: issuer_allowlist_v1
allowlist_path: configs/benchmarks/issuer_allowlist_v1.json

issuer_sample_count: 12

filing_filters:
  form_types: ["10-K", "10-Q"]
  min_fiscal_year: 2022
  max_fiscal_year: 2024
  max_filings_per_issuer: 4

profile_quotas:
  financebench: 0.34
  finder: 0.33
  finagentbench: 0.33

inspiration_profiles:
  financebench: configs/benchmarks/inspiration_profiles/financebench.yaml
  finder: configs/benchmarks/inspiration_profiles/finder.yaml
  finagentbench: configs/benchmarks/inspiration_profiles/finagentbench.yaml

generation_judge_version: gemini-2.5-pro
generation_judge_config: configs/judges/gemini_2_5_pro.yaml

evaluation_judge_version: gemini-2.5-pro
evaluation_judge_config: configs/judges/gemini_2_5_pro.yaml

governance:
  max_issuers: 12
  max_filings_per_issuer: 4
  max_items: 220
  max_judge_api_calls: 600
  max_storage_bytes: 5368709120
  max_wall_clock_seconds: 14400
  validation_pass_rate: 0.95
  dedup_similarity_threshold: 0.85
  judge_retries_per_item: 2

output:
  drafts_root: data/benchmarks/custom-judge/drafts
  published_root: data/benchmarks/custom-judge
```

## Validation rules

- `profile_quotas` values must sum to `1.0` ± `0.01`
- `issuer_sample_count` ≤ `governance.max_issuers`
- `allowlist_path` must exist; hash computed at run start
- Judge config paths must resolve to files with `model_id` field

## Versioning

Config changes that affect item content require new dataset semver on publish; `config_hash` stored in sampling manifest.
