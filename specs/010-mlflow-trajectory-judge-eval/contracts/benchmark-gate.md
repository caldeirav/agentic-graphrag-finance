# Benchmark Trajectory Gate Contract (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Success criterion**: SC-001 (≥90% `complete` trajectories)

## Reference suite composition

| Source | Location (existing / new) | Role |
|--------|---------------------------|------|
| Gold-path | `tests/fixtures/gold_path/gold_path.jsonl` | Navigation + answer quality |
| Macro-binding | 008 macro eval fixtures / harness | Binding decisions |
| Trajectory-validation | `tests/fixtures/trajectory_validation/*.json` | Structural validator edge cases |

**Minimum items**: 50  
**Fixed corpus**: AAPL materialized snapshot (pin `snapshot_id` in suite config)

## Suite manifest (required for CI)

Combined runnable items live in:

- **`configs/benchmarks/reference_trajectory_gate.yaml`** — suite metadata, pinned `snapshot_id`, gate threshold
- **`tests/fixtures/reference_trajectory_gate/items.jsonl`** — ≥50 rows, each with `item_id`, `source` (`gold_path` \| `macro_binding` \| `trajectory_validation`), and runner inputs

**Composition target** (minimum 50 total):

| Source | Fixture path | Target count |
|--------|--------------|--------------|
| Gold-path | `tests/fixtures/gold_path/gold_path.jsonl` (42 rows) | 42 |
| Macro-binding | `tests/fixtures/macro_validator/` + macro planner stubs | ≥6 |
| Trajectory-validation | `tests/fixtures/trajectory_validation/*.json` (structural; may be validator-only rows) | ≥4 |

Build script: `scripts/build_reference_trajectory_gate.py` (or task T053a) regenerates `items.jsonl` from sources and fails if `count < 50`.

## Gate definition

```python
pass_rate = complete_count / total_items
gate_passed = pass_rate >= 0.90
```

- `complete` = `TrajectoryValidationResult.status == "complete"`
- Items with `incomplete` or `non_reproducible` do NOT count as pass
- Judge scores are **out of scope** for this gate (separate quality metrics)

## Reporting (FR-008, SC-002)

Benchmark summary MUST print:

```
trajectory_validation:
  total: 52
  complete: 48 (92.3%)
  incomplete: 3
  non_reproducible: 1
  gate: PASS

judge (complete only):
  evaluated: 47
  degraded: 1
  mean synthesis_grounding: 0.74
```

## CI integration

- Job runs with `USE_MOCK_JUDGE=1`, `USE_FIXTURE_INGESTION=1` where applicable
- Fails CI when `gate_passed` is false
- Document in `.github/workflows/ci.yml` (implementation task)

## Contract tests

`tests/integration/test_benchmark_trajectory_gate.py`:
- Synthetic suite of 10 fixtures → assert gate math
- Full suite marked `@pytest.mark.slow` optional nightly
