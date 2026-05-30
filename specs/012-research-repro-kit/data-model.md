# Data Model: Research Reproduction Kit (012)

**Feature**: 012-research-repro-kit | **Date**: 2026-05-30

## Entity relationship overview

```text
ReleaseManifest ──references──> CustomJudge DatasetManifest (011)
       │
       ├──> SystemVariant[] (ordered run list)
       ├──> ModelPins (llm, judge, embedding)
       └──> ExpectedTableChecksums

CustomJudge items/dev.jsonl ──materialize──> RelevanceLabelSet
       │
       └──> relevant_chunk_ids per item

ReleaseManifest ──orchestrates──> ReproRun
       │
       └──> EvalRun[] (one per SystemVariant)
                 │
                 └──> BenchmarkResult[] (per item)
                           │
                           └──> PaperTableExport (aggregated)
```

## ReleaseManifest

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | string | yes | `1.0.0` |
| `release_tag` | string | yes | e.g. `paper-v1.0` |
| `git_sha` | string | yes | Full commit at release |
| `custom_judge_version` | string | yes | e.g. `1.0.0` |
| `custom_judge_bundle_path` | path | yes | `data/benchmarks/custom-judge/v1.0.0` |
| `eval_split` | string | yes | `dev` for paper-v1.0 |
| `corpus_hashes` | dict[str, string] | yes | Subset of 011 `artifact_hashes` to verify |
| `relevance_labels_hash` | string | yes | After materialize; gate before eval |
| `variant_ids` | list[string] | yes | Ordered; paper-v1.0: 5 ids |
| `model_pins` | ModelPins | yes | |
| `tolerance_bands` | ToleranceBands | yes | Judge-stochastic metrics |
| `expected_checksums_path` | path | yes | Relative JSON with table hashes |
| `reproduction_mode` | enum | yes | `live_reexecution` |

**Validation rules**:
- `variant_ids` for `paper-v1.0` MUST equal `[graph-full, flat-chunk, ablation-no-macro, ablation-no-walker, ablation-xbrl-only]`
- `eval_split` MUST be `dev`
- `relevance_labels_hash` MUST match sidecar after materialize

## ModelPins

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `llm_config_path` | path | yes | e.g. `configs/llm/lm_studio_qwen.yaml` |
| `llm_config_hash` | string | yes | SHA-256 of file |
| `judge_config_path` | path | yes | e.g. `configs/judges/gemini_2_5_pro.yaml` |
| `judge_config_hash` | string | yes | |
| `embedding_model_id` | string | yes | HF model id |
| `embedding_model_revision` | string | yes | HF commit/revision pin for reproducible vectors |
| `embedding_config_path` | path | yes | top-k, batch size, cache policy |
| `embedding_config_hash` | string | yes | SHA-256 of embedding config file |

## ToleranceBands

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `mean_outcome_accuracy` | float | yes | Absolute ±, e.g. 0.02 |
| `mean_rubric_alignment` | float | yes | |
| `mean_trajectory_fidelity` | float | yes | |
| `ranking_metrics_exact` | bool | yes | Always `true` |
| `structural_metrics_exact` | bool | yes | Always `true` |

## SystemVariant

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `variant_id` | string | yes | Stable slug |
| `description` | string | yes | Methods section text |
| `backend` | enum | yes | `langgraph` \| `flat_chunk` |
| `config_path` | path | yes | YAML capability flags |
| `top_k` | int | no | flat-chunk only; default 10 |

**Capability flags** (`VariantCapabilities` in config YAML):

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `disable_macro_router` | bool | false | Skip macro planning |
| `disable_graph_walker` | bool | false | No meso/micro hops |
| `xbrl_only` | bool | false | Exclude HTML narrative chunks |

## RelevanceLabelSet

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `labels_hash` | string | yes | SHA-256 canonical JSON |
| `snapshot_id` | string | yes | Graph snapshot used |
| `coverage_rate` | float | yes | Fraction with non-empty ids |
| `items_labeled` | int | yes | |
| `items_failed` | list[RelevanceFailure] | yes | Below gate diagnostics |
| `labels_by_item_id` | dict[str, list[string]] | yes | Ordered chunk node ids |

**RelevanceFailure**: `item_id`, `expected_section_paths`, `reason` (`unresolved_path`, `no_chunks_under_path`).

**Materialization rules (FR-006)**:
- Include node types: `CHUNK_PARAGRAPH`, `CHUNK_XBRL_FACT`, `CHUNK_TABLE`, `CHUNK_ROW`
- Traversal: structural `CONTAINS` from resolved section nodes only
- Ordering: lexicographic `node_id`

## ReproRun

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `repro_run_id` | string | yes | UUID |
| `release_tag` | string | yes | |
| `manifest_hash` | string | yes | |
| `started_at` | datetime | yes | |
| `completed_at` | datetime | no | |
| `variant_runs` | list[EvalRunRef] | yes | |
| `offline_mode` | bool | yes | `OFFLINE_BENCHMARK=1` |
| `status` | enum | yes | `running` \| `completed` \| `failed` |

## EvalRun (extended from 001/010)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `variant_id` | string | yes | NEW |
| `custom_judge_version` | string | yes | |
| `split` | string | yes | |
| `snapshot_id` | string | yes | |
| `mlflow_parent_run_id` | string | yes | |
| `items_excluded_incomplete` | int | yes | Audit |
| `items_excluded_degraded` | int | yes | |
| `structural_metrics` | StructuralMetrics | yes | Per-variant aggregates |

## StructuralMetrics

| Field | Type | Notes |
|-------|------|-------|
| `accession_binding_accuracy` | float | Expected accessions used |
| `section_path_hit_rate` | float | Expected paths in trajectory |
| `multi_filing_success_rate` | float | finagentbench-profile items |

## PaperTableExport

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `release_tag` | string | yes | |
| `exported_at` | datetime | yes | |
| `headline_rows` | list[MetricRow] | yes | |
| `by_profile_rows` | list[ProfileMetricRow] | yes | |
| `variant_delta_rows` | list[DeltaRow] | yes | |
| `audit_rows` | list[AuditRow] | yes | |

**MetricRow**: `variant_id`, `metric_name`, `value`, `item_count`, `n/a_reason` (optional).

**ProfileMetricRow**: adds `inspiration_profile`.

**DeltaRow**: `baseline_variant`, `comparison_variant`, `metric_name`, `delta`.

## Extensions to 011 DatasetManifest

Add optional fields (backward compatible):

| Field | Type | Notes |
|-------|------|-------|
| `relevance_labels_hash` | string | After materialize |
| `relevance_coverage_rate` | float | |
| `relevance_snapshot_id` | string | |
| `relevance_labels_path` | path | Default `relevance_labels.json` |

## BenchmarkItem (012 usage)

Uses existing `BenchmarkItem` from `models/evaluation.py` with:
- `expected_section_paths` (011)
- `relevant_chunk_ids` (populated by materialize)
- `inspiration_profile` (stratum key)
- `multi_filing_required` (structural scoring)

No schema break; JSONL rows updated in place during materialize when run as post-publish step.
