# Quickstart: XBRL Numeric Binding & Computation (021)

## Prerequisites

- 020 shipped on branch `019-agent-failure-investigation`
- `export OFFLINE_BENCHMARK=1`
- Graph snapshots + LLM keys for cohort re-run

## Cohort fixture

`specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json` (26 items)

## Implementation order

1. **Step 1** — FY binding (`temporal_scope.py`, macro validator)
2. **Step 2** — XBRL catalog + resolution
3. **Step 3** — Metric intent + Python computation
4. **Step 4** — Gate live deterministic numeric overrides

See [tasks.md](./tasks.md) for task IDs T005–T022.

## Unit tests (during implementation)

```bash
uv run pytest tests/unit/test_temporal_scope.py \
  tests/unit/test_xbrl_fact_catalog.py \
  tests/unit/test_metric_intent.py \
  tests/unit/test_numeric_computation.py \
  tests/regression/failure_modes/test_live_no_deterministic_numeric.py -q
```

## Cohort validation (after steps 1–4)

Re-run (not replay):

```bash
uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-xbrl-021-debug \
  --no-resume
```

Check binding:

```bash
rg -l binding_miss reports/cohort-xbrl-021-debug/cohort_debug/ | wc -l
```

Re-judge if needed:

```bash
uv run agent-query repro judge-batch \
  --input reports/cohort-xbrl-021-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --variant graph-full \
  --item-ids-file specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --force-rescore
```

## Success targets (spec SC-001–SC-004)

- ≥15/26 with `outcome_score > 0`
- ≤8/26 abstention-like answers
- ≥20/26 FY2025 items bind 10-K
- No live “Per XBRL … bound fiscal period” answers

## References

- [spec.md](./spec.md)
- [plan.md](./plan.md)
- `.cursor/rules/agent-capability-first.mdc`
