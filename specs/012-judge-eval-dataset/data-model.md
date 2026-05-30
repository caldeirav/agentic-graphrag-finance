# Data Model: Judge-Generated Custom Evaluation Dataset (012)

**Feature**: 012-judge-eval-dataset | **Date**: 2026-05-20

## Entity relationship overview

```text
IssuerAllowlist ──< SamplingManifest >── GenerationConfig
                         │
                         v
                  CorpusBundle (snapshot_id, LFS paths)
                         │
                         v
              GeneratedBenchmarkItem (draft candidates)
                         │
                         v
                  DatasetManifest (published version)
                         │
                         └──> BenchmarkItem (registry adapter view)
```

## IssuerAllowlist

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `allowlist_id` | string | yes | e.g. `issuer_allowlist_v1` |
| `content_hash` | string | yes | SHA-256 of canonical JSON |
| `entries` | list[AllowlistEntry] | yes | |
| `provenance` | string | yes | Sources used to build list |

**AllowlistEntry**: `ticker`, `cik` (optional), `sources` (list: `financebench`, `finder`, `finagentbench`, `fixture`).

## GenerationConfig

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `config_id` | string | yes | e.g. `custom_judge_v1` |
| `random_seed` | int | yes | FR-008 |
| `allowlist_id` | string | yes | References IssuerAllowlist |
| `issuer_sample_count` | int | yes | ≤ `max_issuers` |
| `filing_filters` | FilingFilters | yes | form types, period range |
| `profile_quotas` | dict[str, float] | yes | Must sum ≈ 1.0; v1 equal thirds |
| `governance` | GovernanceCaps | yes | FR-007 |
| `generation_judge_version` | string | yes | e.g. `gemini-2.5-pro` |
| `evaluation_judge_version` | string | yes | v1 default same as generation |
| `inspiration_profile_paths` | dict[str, string] | yes | Profile id → YAML path |

**FilingFilters**: `form_types: list[str]`, `min_fiscal_year`, `max_fiscal_year`, `max_filings_per_issuer`.

**GovernanceCaps**: `max_issuers`, `max_filings_per_issuer`, `max_items`, `max_judge_api_calls`, `max_storage_bytes`, `max_wall_clock_seconds`, `validation_pass_rate`, `dedup_similarity_threshold`, `judge_retries_per_item`.

## SamplingManifest

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `manifest_id` | string | yes | UUID |
| `config_hash` | string | yes | Hash of GenerationConfig |
| `allowlist_hash` | string | yes | FR-016 |
| `random_seed` | int | yes | |
| `selected_issuers` | list[SelectedIssuer] | yes | Ordered deterministically |
| `created_at` | datetime | yes | |
| `budget_snapshot` | BudgetSnapshot | yes | Counters at sampling end |

**SelectedIssuer**: `ticker`, `cik`, `accessions` (ordered), `selection_rationale` (tags).

## CorpusBundle

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `snapshot_id` | string | yes | Primary graph snapshot (multi-issuer: composite id) |
| `issuer_snapshots` | list[IssuerSnapshotRef] | yes | Per-ticker snapshot id + path |
| `corpus_root` | path | yes | Relative to bundle root |
| `graph_node_index_path` | path | yes | For section path validation |
| `reachability_audit_path` | path | no | From 004 materialization |
| `total_bytes` | int | yes | Governance |
| `artifact_hashes` | dict[str, string] | yes | SHA-256 per LFS object |

## GeneratedBenchmarkItem (draft / JSONL row)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `item_id` | string | yes | Stable `{version}-{profile}-{seq}` |
| `dataset` | string | yes | `custom-judge` |
| `question` | string | yes | |
| `question_type_tag` | string | yes | Profile-specific taxonomy tag |
| `inspiration_profile` | string | yes | `financebench` \| `finder` \| `finagentbench` |
| `ground_truth` | GroundTruth | yes | answer and/or rubric |
| `expected_bindings` | ExpectedBindings | yes | accessions + fiscal periods |
| `expected_section_paths` | list[string] | yes | Graph-resolvable paths |
| `relevant_chunk_ids` | list[string] | no | Filled post-validation when bindable |
| `multi_filing_required` | bool | yes | true for finagentbench profile |
| `operation_class` | OperationClass | yes | Derived from question type |
| `validation_status` | string | yes | `accepted` \| `rejected` |
| `validation_errors` | list[string] | no | |

**Validation rules (FR-009)**:
- `question` non-empty
- `expected_bindings.accessions` ⊆ snapshot accessions
- Every `expected_section_path` exists in `graph_node_index`
- At least one of `ground_truth.answer` or `ground_truth.rubric` non-empty
- `finagentbench` profile ⇒ len(accessions) ≥ 2

## DatasetManifest (published)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | string | yes | `1.0.0` |
| `dataset_name` | string | yes | `custom-judge` |
| `version` | string | yes | Semver e.g. `1.0.0` |
| `status` | enum | yes | `draft` \| `published` |
| `parent_version` | string | no | For extend |
| `item_count` | int | yes | ≥200 for v1 publish |
| `items_hash` | string | yes | SHA-256 of canonical items JSONL |
| `sampling_manifest_path` | string | yes | |
| `generation_config_path` | string | yes | |
| `corpus_bundle` | CorpusBundle | yes | |
| `generation_judge_version` | string | yes | |
| `evaluation_judge_version` | string | yes | |
| `profile_counts` | dict[str, int] | yes | Actual per-profile totals |
| `published_at` | datetime | no | Set on publish |
| `published_by` | string | no | Operator id / git user |

## GenerationReport

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | |
| `candidates_total` | int | yes | |
| `accepted_count` | int | yes | |
| `rejected_count` | int | yes | |
| `pass_rate` | float | yes | Must ≥ validation_pass_rate to allow publish |
| `rejections_by_reason` | dict[str, int] | yes | |
| `judge_api_calls` | int | yes | |
| `storage_bytes_used` | int | yes | |
| `duration_seconds` | float | yes | |
| `budget_exceeded` | bool | yes | |

## State transitions

```text
GenerationConfig + Allowlist
    → sampling → SamplingManifest
    → materialize → CorpusBundle (invalid if partial failure per edge case)
    → judge generate → draft items
    → validate + dedup → GenerationReport
    → if pass_rate OK → draft bundle (status=draft)
    → operator publish → DatasetManifest (status=published) + registry
```

**Extend**: `published v1` + delta config → new draft run → `published v2` with `parent_version=v1`; parent artifacts immutable.

## Registry view (`BenchmarkItem`)

Published JSONL rows map to existing `models.evaluation.BenchmarkItem` with extensions stored in row metadata:

- `expected_section_paths` → new optional field on `BenchmarkItem` (012 adds to model)
- `temporal_scope` from fiscal periods in bindings
- `dataset` = `custom-judge`

## Index files (bundle)

| File | Purpose |
|------|---------|
| `manifest.json` | DatasetManifest |
| `generation_config.yaml` | Frozen config copy |
| `sampling_manifest.json` | SamplingManifest |
| `generation_report.json` | GenerationReport |
| `items/dev.jsonl` | Accepted items (primary split v1) |
| `items/test.jsonl` | Optional holdout (future) |
| `corpus/**` | LFS: raw SEC, parsed, graph exports |
