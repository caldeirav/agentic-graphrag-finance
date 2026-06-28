# Contract: Tier-1 Cohort Gate

**Feature**: 019 | **Commands**: `repro cohort-freeze`, `repro cohort-validate`, gate hook in `repro run-all`

## Freeze cohort

```bash
uv run agent-query repro cohort-freeze \
  --queue data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --output data/benchmarks/custom-judge/drafts/quality-v2.0.1/tier1_cohort.json
```

Produces `Tier1CohortFile` with **all** tier-1 item ids and queue provenance hash.

## Validate cohort

```bash
uv run agent-query repro cohort-validate \
  --cohort tier1_cohort.json \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-cohort-validate/run-001 \
  [--baseline reports/repro-paper-v1.0/cohort_validation_report.json]
```

Runs agent+judge on full cohort (graph-full). Writes `cohort_validation_report.json`.

## Manifest thresholds (`releases/paper-v1.1/manifest.yaml`)

```yaml
cohort_gate_thresholds:
  baseline_snapshot_path: reports/repro-paper-v1.0/cohort_validation_report.json
  max_strong_retrieval_zero_outcome: 63
  max_mrr_ok_va_zero: 10
  min_synthesis_template_dump_share_reduction: 0.15
  require_regression_suite_pass: true
```

## Gate enforcement on full repro

When `repro run-all --manifest releases/paper-v1.1/manifest.yaml`:

1. Load latest `cohort_validation_report.json` referenced by manifest or `--cohort-report`
2. If `passed != true` → **exit code 1** with failed threshold list
3. Override: `--force-cohort-gate "rationale text"` appends `CohortGateOverrideRecord` to `{output}/cohort_gate_overrides.jsonl` and proceeds

## Audit artifacts

| File | Purpose |
|------|---------|
| `cohort_validation_report.json` | Metric snapshot + pass/fail |
| `cohort_gate_overrides.jsonl` | Force override audit trail |

## CI

- Unit tests mock thresholds; no 84-item agent run in CI
- Integration test uses 3-item fixture cohort + mock results
