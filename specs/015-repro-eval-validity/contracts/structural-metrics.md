# Structural Metrics Contract (015)

**Feature**: 015-repro-eval-validity | **Spec**: FR-005, SC-003

## Purpose

Record accession binding accuracy, section path hit rate, and multi-filing success rate per variant in `repro_run.json` — not zero placeholders when binding-heavy items exist.

## Existing implementation

`src/evaluation/reproduction/structural.py`:

| Function | Meaning |
|----------|---------|
| `accession_binding_hit` | Expected accessions ⊆ used accessions |
| `section_path_hit` | Expected section path appears in visited paths |
| `multi_filing_success` | ≥2 expected accessions used when `multi_filing_required` |
| `aggregate_structural_metrics` | Macro averages over item list |

## Persistence

`models.reproduction.EvalRunRef.structural_metrics`:

```json
{
  "accession_binding_accuracy": 0.85,
  "section_path_hit_rate": 0.72,
  "multi_filing_success_rate": 0.60
}
```

Written when variant run completes in `ReproRunner` (all five standard variants).

## Per-item extraction (NEW)

From each `BenchmarkResult.trajectory_snapshot` after `normalize_trajectory_state`:

### `used_accessions`

Union of:

1. Accession strings from `filing_set` / `document_route` entries
2. Parsed from citation / evidence chunk node ids matching `doc-{accession}-...`

### `visited_paths`

Union of:

1. `graph_traversal` node ids
2. Section ids from evidence chunks (`section_id` property when present)

Helper location: `evaluation/reproduction/structural_extract.py` (or methods on structural module).

## Aggregation inputs

```python
aggregate_structural_metrics(
    benchmark_items,  # from custom-judge split for run
    used_accessions_by_item=item_id -> set[str],
    visited_paths_by_item=item_id -> set[str],
)
```

Items without trajectory: empty sets (count as misses when expectations exist).

## Report surfacing

- `detect_run_anomalies` / aggregated notes: single warning if **all** variants show structural zeros when `expected_bindings` items exist
- Run summary may display structural metrics per variant from `repro_run.json`

## Verification (SC-003)

Smoke reproduction with binding-heavy items:

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-live-smoke/manifest.yaml \
  --max-items 10
```

Expect `repro_run.json` → each completed variant → `structural_metrics` with at least one field > 0 when items carry `expected_bindings`.

## Non-goals

- Does not change graph walker behavior
- Does not recompute from MLflow at report time (checkpoint snapshots only)
