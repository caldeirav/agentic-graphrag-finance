# Paper Table Export Contract (012)

**Producer**: `src/evaluation/reproduction/export.py`  
**Consumer**: Researchers, `repro verify-tables`, paper LaTeX pipeline

## headline.csv

Columns:

| Column | Type | Notes |
|--------|------|-------|
| `variant_id` | string | |
| `metric_name` | string | See metric catalog below |
| `value` | float | Aggregate mean or rate |
| `item_count` | int | Items included in aggregate |
| `excluded_incomplete` | int | Audit |
| `excluded_degraded` | int | Audit |
| `na_reason` | string | Empty if applicable |

One row per `(variant_id, metric_name)`.

## by_profile.csv

Adds column `inspiration_profile` (`financebench` | `finder` | `finagentbench`).

For finder stratum rows where no `ground_truth.answer`:
- `outcome_accuracy` row omitted OR `na_reason= r rubric_only`

## variant_delta.csv

| Column | Type |
|--------|------|
| `baseline_variant` | string |
| `comparison_variant` | string |
| `metric_name` | string |
| `delta` | float (baseline − comparison) |

Required pairs for paper-v1.0:
- `(graph-full, flat-chunk)` — primary claim
- `(graph-full, ablation-no-macro)`
- `(graph-full, ablation-no-walker)`
- `(graph-full, ablation-xbrl-only)`

## trajectory_audit.csv

| Column | Type |
|--------|------|
| `variant_id` | string |
| `excluded_incomplete` | int |
| `excluded_degraded` | int |
| `included_in_headline` | int |

## Metric catalog (FR-009)

| metric_name | Source | Headline eligibility |
|-------------|--------|----------------------|
| `outcome_accuracy` | judge / answer match | Items with `ground_truth.answer`; exclude incomplete |
| `rubric_alignment` | judge claim_presence | Items with `ground_truth.rubric` |
| `mrr` | ranking | Items with non-empty `relevant_chunk_ids` |
| `map` | ranking | same |
| `ndcg_at_10` | ranking | same |
| `accession_binding_accuracy` | trajectory | All items |
| `section_path_hit_rate` | trajectory | Items with `expected_section_paths` |
| `multi_filing_success_rate` | trajectory | `multi_filing_required=true` |
| `trajectory_fidelity` | feature 010 | Exclude incomplete |

## Aggregation rules (FR-010)

- Exclude items where `validation_status=INCOMPLETE` from headline accuracy, fidelity, and ranking means.
- Exclude `judge_status=degraded` from headline means; count in audit.
- Ranking metrics: skip items with empty `relevant_chunk_ids` (denominator adjusted).

## verify-tables

Compare exported values to `expected_checksums.json`:
- Structural + ranking: exact match (±1e-9)
- Outcome/rubric/fidelity: within manifest `tolerance_bands`

Return exit code 0 on pass, 1 on mismatch with diff report.
