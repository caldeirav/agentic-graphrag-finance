# Data Model: Benchmark Evaluation Acceleration (013)

**Feature**: 013-benchmark-eval-acceleration | **Date**: 2026-06-01

## Entity relationship overview

```text
ReleaseManifest (012)
       │
       └──> ReproRun (EXTENDED)
                 ├──> AccessionIndex (NEW, session-scoped)
                 ├──> ItemGraphSlice (NEW, per item)
                 └──> EvalRunRef[] (per variant)
                           └──> BenchmarkResult[] (EXTENDED judge + trajectory)

ReproRun ──orchestrates──> JudgeBatchJob (NEW, optional phase)
       │
       └──> PaperTableExport (gated on judge completeness)
```

## AccessionIndex (NEW)

Built once per reproduction session from bundle manifests.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `accession_to_issuer` | dict[str, IssuerSnapshotRef] | yes | Accession → ticker + snapshot_id |
| `bundle_root` | path | yes | custom-judge bundle root |
| `composite_snapshot_id` | string | yes | Full corpus id from manifest |

**IssuerSnapshotRef**

| Field | Type | Required |
|-------|------|----------|
| `ticker` | string | yes |
| `snapshot_id` | string | yes |
| `graph_path` | path | yes (derived) |

**Validation rules**:
- Every accession in `items/*.jsonl` `expected_bindings.accessions` MUST resolve or repro fails with `MissingAccessionsError(item_id, missing[])`.
- Duplicate accessions across issuers MUST error at index build (ambiguous mapping).

## ItemGraphSlice (NEW)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `slice_id` | string | yes | e.g. `slice-a1b2c3` from accession set hash |
| `accessions` | list[string] | yes | Sorted unique |
| `tickers` | list[string] | yes | Derived |
| `snapshot` | GraphSnapshot | yes | Merged in-memory graph |
| `node_count` | int | yes | Denormalized for logging |
| `filing_count` | int | yes | `len(manifest.filing_refs)` |

**State**: Ephemeral; cached in `ReproRunner._slice_cache[frozenset(accessions)]`.

## BenchmarkResult (EXTENDED)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `judge_status` | string | yes | Add **`pending`** to allowed values (extends `JudgeStatus` enum) |
| `trajectory_snapshot` | dict | defer mode | Serialized 010 snapshot for batch judge |
| `generation_mlflow_run_id` | string | defer mode | Agent run id |
| *(existing fields)* | | | answer, ranking_metrics, judge_verdict, … |

**State transitions (judge_status)**:

```text
(pending) ──batch judge──> ok | degraded | not_evaluable
```

Generation without defer: `ok | degraded` via inline audit (unchanged).

## JudgeBatchJob (NEW)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `output_dir` | path | yes | reports/repro-{tag} |
| `variant_id` | string | optional | All variants if omitted |
| `concurrency` | int | yes | default 2 |
| `started_at` | datetime | yes | |
| `completed_at` | datetime | no | |
| `items_judged` | int | yes | |
| `items_skipped` | int | yes | Already final |
| `items_failed` | int | yes | |

## ReproRun (EXTENDED from 012)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `current_variant` | string | no | In-progress variant |
| `completed_variants` | list[string] | yes | Fully done (gen + judge) |
| `items_completed` | dict[str, int] | yes | variant_id → count |
| `defer_judge` | bool | yes | Run configuration |
| `judge_phase_status` | enum | yes | `not_started` \| `partial` \| `complete` |
| `last_error` | string | no | Last item/variant failure message |
| *(existing)* | | | repro_run_id, variant_runs, status, … |

**Validation rules**:
- `completed_variants` entry requires variant `results.json` with planned item count and no `pending` judge rows when `defer_judge=true`.
- `repro_run.json` written atomically after each item and on variant boundary.

## DeferJudgeConfig (NEW)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `enabled` | bool | false | From env or CLI |
| `judge_after` | enum | `each_variant` | `each_variant` \| `all_variants` |
| `concurrency` | int | 2 | Judge batch only |
| `allow_pending_export` | bool | false | Partial tables |

## QueryRequest metadata (repro extensions)

| Key | Values | Purpose |
|-----|--------|---------|
| `defer_judge` | `true`/`false` | Skip post-query audit |
| `benchmark_item` | item_id | Repro guard for defer env |
| `slice_snapshot_id` | string | Per-item graph slice id |

## Environment variables (NEW)

| Variable | Default | Purpose |
|----------|---------|---------|
| `REPRO_DEFER_JUDGE` | `0` | Enable defer judging |
| `REPRO_JUDGE_CONCURRENCY` | `2` | Batch judge parallelism |
| `REPRO_JUDGE_AFTER` | `each_variant` | Batch timing |
