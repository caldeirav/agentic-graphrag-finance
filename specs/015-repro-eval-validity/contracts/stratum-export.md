# Stratified Export Contract (015)

**Feature**: 015-repro-eval-validity | **Spec**: FR-012–FR-015, SC-005, SC-006

## New tables

### `tables/by_evidence_source.csv`

Per-variant, per-stratum headline metrics plus abstention rate.

**Columns** (order fixed):

```text
variant_id,primary_evidence_source,metric_name,value,item_count,abstention_rate,excluded_incomplete,excluded_degraded,excluded_pending_judge,na_reason
```

**Metrics** (same catalog as headline):

- `outcome_accuracy`
- `rubric_alignment`
- `trajectory_fidelity`
- `mrr`
- `map`
- `ndcg_at_10`
- `abstention_rate` (also duplicated as dedicated rows with `metric_name=abstention_rate`)

**Strata included**: `html`, `xbrl`, `mixed` only.

**Excluded**: `unknown` stratum items (count in `export_manifest.json` → `stratum_audit.unknown_excluded`).

### `tables/variant_delta_by_source.csv`

Stratum-scoped deltas vs `graph-full` baseline.

**Columns**:

```text
primary_evidence_source,baseline_variant,comparison_variant,metric_name,delta,baseline_item_count,comparison_item_count,na_reason
```

**Rules**:

- `baseline_variant` is always `graph-full`
- One row per (stratum, comparison_variant, metric_name)
- `na_reason=low_n` when stratum eligible count < 10 (default threshold)
- Does not replace `variant_delta.csv` (pooled full-split)

### Unchanged: `tables/variant_delta.csv`

Schema remains:

```text
baseline_variant,comparison_variant,metric_name,delta
```

Pooled across all eligible dev items regardless of stratum.

## Stratum assignment

At export time, for each custom-judge dev item:

```python
primary_evidence_source = assign_primary_evidence_source(item.relevant_chunk_ids)
```

Uniform rule (spec clarification):

| Labeled chunks | Stratum |
|----------------|---------|
| all HTML | `html` |
| all XBRL | `xbrl` |
| both types | `mixed` |
| empty | `unknown` |

## Abstention rate

For each (variant, stratum):

```text
abstention_rate = abstained_eligible / eligible_in_stratum
```

Abstention detection: reuse `outcome_scoring.is_abstention(answer)` on stored results.

## Headline eligibility

Same 012 rules as pooled export:

- Exclude `validation_status != complete`
- Exclude `judge_status == degraded`
- Exclude `judge_status == pending` unless allow-pending flag
- Finder profile: `outcome_accuracy` rows may carry `na_reason=rubric_only`

## Report consumption (014 extension)

`PaperTableId` enum adds:

- `BY_EVIDENCE_SOURCE`
- `VARIANT_DELTA_BY_SOURCE`

Loader: optional tables (warn if missing on pre-P3 checkpoints).

Renderer: stratified ablation section with variant×metric matrix per stratum, item counts, abstention rate column.

## Manifest guidance (FR-016)

`releases/paper-v1.0/manifest.yaml` adds `ablation_guidance`:

```yaml
ablation_guidance:
  html:
    valid_comparisons:
      - baseline: graph-full
        comparison: ablation-no-walker
    ranking_margin:
      graph_full_mrr_min: 0.10
      ablation_no_walker_mrr_max: 0.05
      abstention_rate_min: 0.80  # ablation-no-walker on HTML stratum (SC-006)
    notes: "Walker required for HTML narrative chunks"
  xbrl:
    valid_comparisons:
      - baseline: graph-full
        comparison: ablation-xbrl-only
  mixed:
    valid_comparisons:
      - baseline: graph-full
        comparison: ablation-no-macro
```

## Validation

- Sum of `item_count` across strata (per variant, per metric) ≤ total eligible dev items
- SC-005: all five variants present for html, xbrl, mixed strata
- SC-006: HTML stratum on paper-v1.0 after re-judge — `ablation-no-walker.abstention_rate` ≥ 0.80, `graph-full.mrr` ≥ 0.10, `ablation-no-walker.mrr` ≤ 0.05 (thresholds in manifest `ranking_margin`)
