# Data Model: Reproduction Evaluation Validity & Stratified Ablations (015)

**Feature**: 015-repro-eval-validity | **Date**: 2026-06-06

## Entity relationship overview

```text
BenchmarkItem
    └── relevant_chunk_ids[] ──► EvidenceStratum (derived)

ReproRun
    └── variant_runs[]
            └── EvalRunRef
                    └── StructuralMetrics (populated)

ExportBundle (012 extended)
    ├── headline_rows / by_profile_rows / variant_delta_rows (unchanged)
    ├── by_evidence_source_rows[]     # NEW
    └── variant_delta_by_source_rows[] # NEW

ReproOutputBundle (014 extended)
    ├── tables["by_evidence_source"]
    ├── tables["variant_delta_by_source"]
    └── aggregated_notes[]            # NEW (replaces flat RunAnomaly list at render)
```

## EvidenceStratum

Per-item classification derived at export or publish time.

| Value | Rule |
|-------|------|
| `html` | Every `relevant_chunk_id` classifies as HTML narrative |
| `xbrl` | Every id classifies as XBRL fact chunk |
| `mixed` | Both types present |
| `unknown` | Empty `relevant_chunk_ids` |

**Chunk classification** (normative per spec clarification 2026-06-06; applied before uniform stratum rule):

| Condition on chunk id | Type |
|-----------------------|------|
| contains `-html-` or starts with `html-` | html |
| contains `xbrl` (case-insensitive) | xbrl |
| any other non-empty id | html (legacy narrative ids e.g. `sec-*` without explicit markers) |
| (no ids — empty `relevant_chunk_ids` list) | stratum `unknown` only; no per-chunk classification |

Validation: `classify_chunk_id(id) -> Literal["html","xbrl"]`; `assign_primary_evidence_source(ids) -> Literal["html","xbrl","mixed","unknown"]` is pure and unit-tested.

## AbstentionRate

| Field | Type | Notes |
|-------|------|-------|
| `variant_id` | string | Standard five variants |
| `primary_evidence_source` | string | html, xbrl, mixed (not unknown) |
| `rate` | float | 0.0–1.0 |
| `abstained_count` | int | |
| `eligible_count` | int | Headline-eligible items in stratum |

## StructuralAuditMetrics

Alias of existing `StructuralMetrics` on `EvalRunRef`.

| Field | Type | Range |
|-------|------|-------|
| `accession_binding_accuracy` | float | 0.0–1.0 |
| `section_path_hit_rate` | float | 0.0–1.0 |
| `multi_filing_success_rate` | float | 0.0–1.0 |

Populated per variant when variant run completes. Zero only when no applicable items exist (not a placeholder default when bindings exist).

**Per-item inputs** (transient, not persisted):

| Map | Key | Value |
|-----|-----|-------|
| `used_accessions_by_item` | item_id | set of accession strings |
| `visited_paths_by_item` | item_id | set of section/path node ids |

## StratumTableRow

Export row for `by_evidence_source.csv`.

| Field | Type | Required |
|-------|------|----------|
| `variant_id` | string | yes |
| `primary_evidence_source` | string | yes |
| `metric_name` | string | yes |
| `value` | float | yes |
| `item_count` | int | yes |
| `abstention_rate` | float | yes |
| `excluded_incomplete` | int | yes |
| `excluded_degraded` | int | yes |
| `excluded_pending_judge` | int | yes |
| `na_reason` | string | no |

## StratumDeltaRow

Export row for `variant_delta_by_source.csv`.

| Field | Type | Required |
|-------|------|----------|
| `primary_evidence_source` | string | yes |
| `baseline_variant` | string | yes (`graph-full`) |
| `comparison_variant` | string | yes |
| `metric_name` | string | yes |
| `delta` | float | yes |
| `baseline_item_count` | int | yes |
| `comparison_item_count` | int | yes |
| `na_reason` | string | no (`low_n` when stratum < 10) |

## AggregatedInvestigationNote

Report view model (replaces per-item `RunAnomaly` for item-driven patterns).

| Field | Type | Required |
|-------|------|----------|
| `severity` | enum: info, warning, critical | yes |
| `variant_id` | string | no (run-level notes omit) |
| `pattern_code` | string | yes |
| `message` | string | yes (includes count) |
| `item_count` | int | yes |
| `example_item_ids` | list[string] | max 5 |
| `hint` | string | no |
| `expandable` | bool | default true when examples present |

**Pattern codes** (non-exhaustive):

| Code | Trigger |
|------|---------|
| `JUDGE_OK_ZERO_CITATIONS` | judge ok, citation_count=0 |
| `HIGH_OUTCOME_ZERO_NDCG` | outcome≥0.9, ndcg=0 (excl. expected ablations) |
| `ABLATION_ZERO_CITATIONS` | no-walker/xbrl-only aggregate zero cites |
| `ABLATION_ZERO_RANKING` | MRR=0 with expected hint |
| `OUTCOME_EXCEEDS_BASELINE` | pooled outcome > graph-full + 0.05 with retrieval signal |
| `STRUCTURAL_METRICS_ZERO` | all variants structural zeros |
| `RUBRIC_ALIGNMENT_ZERO` | all variants rubric 0 |

## Re-judge resume state

On `BenchmarkResult` / `judge_verdict`:

| Field | Resume skip when |
|-------|------------------|
| `judge_verdict.judge_version` | ≥ `v2` |
| `trajectory_snapshot` (normalized).evidence_chunks | non-empty |

Citation-only fallback: if evidence empty but `answer.citations` non-empty, item remains **pending**.

## State transitions

```text
results.json (pre-P0 scores)
    │ judge-batch (re-score)
    ▼
results.json (v2 scores, hydrated evidence)
    │ export-tables
    ▼
tables/*.csv + optional new stratum CSVs
    │ repro report
    ▼
report.html (≤25 aggregated notes + stratum section)
```

## Validation rules

- Stratum aggregates MUST NOT include `unknown` items; audit count recorded in export manifest.
- `variant_delta.csv` MUST remain pooled-only (no stratum column).
- Structural metrics on `repro_run.json` MUST be non-zero for smoke binding-heavy runs when items have `expected_bindings`.
- Aggregated investigation notes MUST NOT exceed 25 top-level entries (SC-004).
