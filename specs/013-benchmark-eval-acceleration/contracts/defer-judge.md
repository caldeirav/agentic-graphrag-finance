# Deferred Judging Contract (013)

**Scope**: Reproduction evaluation only. Interactive `agent-query ask` MUST NOT defer judging unless explicitly documented otherwise (default: never).

## Activation

| Mechanism | Precedence |
|-----------|------------|
| CLI `--defer-judge` on `repro run`, `repro run-all` | Sets session flag |
| `REPRO_DEFER_JUDGE=1` | Default for scripted repro when CLI omitted |
| `QueryRequest.metadata["defer_judge"]="true"` | Per-request (set by ReproRunner) |

**Guard**: `QueryService` MUST only skip `run_post_query_audit` when defer is true **and** `metadata["benchmark_item"]` is non-empty (repro context).

## Generation phase behavior

When defer is active:

1. `QueryService.answer` runs full LangGraph (or flat-chunk baseline) and MLflow trajectory logging unchanged.
2. `run_post_query_audit` MUST NOT be called.
3. Response `judge_status` MUST be `pending`.
4. `BenchmarkResult` written to `results.json` MUST include:
   - `trajectory_snapshot` (dict, 010 schema)
   - `generation_mlflow_run_id` when available
   - `answer`, `ranking_metrics`, `validation_status` from generation
   - `judge_verdict` absent or null until batch phase

Flat-chunk baseline MUST NOT call `GeminiJudgePanel.judge` during `answer()` when defer is active.

## Judge batch phase

**Entry points**:

- Automatic: end of each variant (default) or end of `run-all` (configurable)
- `uv run agent-query repro judge-batch --output <dir> [--variant <id>] [--concurrency N]`
- `uv run agent-query repro run-all --judge-only` (skip generation)

**Per item**:

1. Skip if `judge_status` ∈ `{ok, degraded, not_evaluable}`.
2. Load `trajectory_snapshot` + `answer`; if snapshot missing/invalid → `not_evaluable`.
3. Invoke `GeminiJudgePanel.judge` once (same criteria as 010 `judge_trajectory`).
4. Merge scores into `BenchmarkResult`; set final `judge_status`.
5. Atomic update of `results.json` (write temp + rename).

**Concurrency**: Default 2; configurable; retries via `with_transient_retry`.

## Export interaction

- Headline aggregates MUST exclude `judge_status=pending`.
- `trajectory_audit.csv` MUST list pending count per variant when present.
- `run-all` MUST NOT export headline tables until judge complete unless `--allow-pending-export`.

## MLflow verification (SC-001)

During generation loop with defer, active run tags MUST NOT include judge audit child runs. Tests:

- **CI** (`test_repro_defer_judge_smoke.py`, 5 items): count judge audit calls in generation loop == 0.
- **Release** (`test_repro_defer_judge_sc001`, 20 items, `@pytest.mark.slow`): same assertion at scale.

## Judge-batch restart verification (SC-002)

Integration test `test_repro_judge_batch_restart.py`: seed 20 `pending` rows, judge 10, simulate crash, re-run batch; assert items 11–20 judged once and items 1–10 `judge_verdict` unchanged.
