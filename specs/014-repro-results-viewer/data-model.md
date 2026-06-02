# Data Model: Research Reproduction Results Viewer (014)

**Feature**: 014-repro-results-viewer | **Date**: 2026-06-02

## Entity relationship overview

```text
ReproOutputBundle
    ├── RunSummaryView
    ├── PaperTableView[] (headline/by_profile/variant_delta/trajectory_audit)
    ├── VariantComparisonView
    └── VariantItemView[]
            └── ItemDetailView[]

ReleaseManifestRef (optional) ───────┘
```

## ReproOutputBundle

Top-level loaded report context.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `output_dir` | path | yes | Root `reports/repro-{tag}` |
| `repro_run` | object | yes | Parsed `repro_run.json` |
| `tables` | dict[str, TableData] | yes | Parsed CSVs |
| `variant_results` | dict[str, list[ItemResultRecord]] | conditional | Needed for drill-down |
| `release_manifest` | object | no | Loaded from pointer or CLI path |
| `warnings` | list[string] | yes | Non-fatal missing optional artifacts |

## RunSummaryView

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `release_tag` | string | yes | From run state / manifest |
| `repro_run_id` | string | yes | |
| `started_at` | datetime | yes | |
| `completed_at` | datetime | no | |
| `duration_seconds` | float | no | Derived when timestamps complete |
| `defer_judge` | bool | no | If recorded in run metadata |
| `resume_mode` | bool | no | If recorded in run metadata |
| `variant_counts` | list[VariantCount] | yes | Item and exclusion counts |
| `mlflow_links` | list[string] | no | Derived from parent run ids |

**VariantCount**

| Field | Type |
|-------|------|
| `variant_id` | string |
| `items_total` | int |
| `excluded_incomplete` | int |
| `excluded_degraded` | int |
| `excluded_pending` | int |

## PaperTableView

Represents one rendered table plus copy payloads.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `table_id` | enum | yes | `headline` / `by_profile` / `variant_delta` / `trajectory_audit` |
| `columns` | list[string] | yes | Source CSV headers |
| `rows` | list[dict] | yes | Source CSV rows |
| `latex_copy` | string | yes | Paste-ready snippet |
| `csv_copy` | string | yes | Canonical CSV text |
| `markdown_copy` | string | yes | Markdown table |
| `provenance` | dict | no | release_tag, item_count, exclusions |

## VariantComparisonView

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metric_names` | list[string] | yes | Primary metrics |
| `series` | list[VariantMetricSeries] | yes | One per variant |
| `baseline_variant` | string | yes | `graph-full` default |

**VariantMetricSeries**

| Field | Type |
|-------|------|
| `variant_id` | string |
| `values_by_metric` | dict[str, float] |
| `delta_vs_baseline` | dict[str, float] |

## ItemResultRecord

Per-variant item row for drill-down.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `variant_id` | string | yes | |
| `item_id` | string | yes | |
| `inspiration_profile` | string | no | if available |
| `judge_status` | string | yes | includes pending/degraded/not_evaluable |
| `validation_status` | string | no | |
| `outcome_score` | float | no | |
| `rubric_scores` | dict[str, float] | no | flattened for display |
| `structural_metrics` | dict[str, float] | no | binding/path metrics |
| `failure_reason` | string | no | derived fallback text |
| `answer_excerpt` | string | no | truncated |
| `citation_count` | int | no | derived from answer payload |
| `trajectory_ref` | string | no | summary or source pointer |
| `flags` | list[string] | yes | e.g. pending, degraded, binding_miss, high_delta |

## ReportArtifact

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `html_path` | path | yes | Generated report file |
| `assets_dir` | path | no | Optional companion files |
| `generated_at` | datetime | yes | |
| `source_hashes` | dict[str, string] | yes | Input integrity tracking |
| `format` | enum | yes | `html` / `latex-only` |

