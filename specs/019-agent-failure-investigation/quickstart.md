# Quickstart: Agent Failure Investigation and Remediation (019)

**Feature**: 019-agent-failure-investigation | **Branch**: `019-agent-failure-investigation`

## Prerequisites

- Completed **paper-v1.0** repro: `reports/repro-paper-v1.0/`
- Quality draft with tier-1 queue: `data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json`
- GT quality pass applied (018 workflow)
- `OFFLINE_BENCHMARK=1`, bundle corpus materialized

## 1. Export unified investigation pack

```bash
uv run agent-query benchmark-dataset review export-investigation \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --repro-input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/investigation
```

Open `failure_investigation.html` — each row includes GT, agent answer, judge rationale, suggested failure class, EDGAR links, corpus excerpts, materialization audit.

Regenerate repro report with embedded drill-down:

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --manifest releases/paper-v1.0/manifest.yaml \
  --with-investigation
```

## 2. Freeze tier-1 cohort (all ~84 items)

```bash
uv run agent-query repro cohort-freeze \
  --queue data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --output data/benchmarks/custom-judge/drafts/quality-v2.0.1/tier1_cohort.json
```

## 3. Debug a small subset (before full cohort)

```bash
# Create 5-item ids file from cohort for iteration
uv run agent-query repro cohort-debug \
  --cohort data/benchmarks/custom-judge/drafts/quality-v2.0.1/tier1_cohort.json \
  --item-ids-file tests/fixtures/cohort_debug_smoke_ids.json \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-cohort-debug/smoke-001 \
  --trace normal --trace-json
```

Replay without re-running agent:

```bash
uv run agent-query repro cohort-debug \
  --cohort tier1_cohort.json \
  --replay-input reports/repro-paper-v1.0 \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-cohort-debug/replay-001
```

## 4. Implement remediations + run regression suite

```bash
uv run pytest tests/regression/failure_modes -q
uv run pytest tests/unit/test_failure_taxonomy.py -q
```

## 5. Validate full cohort (pre-repro gate)

```bash
uv run agent-query repro cohort-validate \
  --cohort data/benchmarks/custom-judge/drafts/quality-v2.0.1/tier1_cohort.json \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-cohort-validate/post-fix-001 \
  --baseline reports/repro-paper-v1.0/cohort_validation_report.json
```

Check `cohort_validation_report.json` → `passed: true`.

If failed, full repro is **blocked**:

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-paper-v1.1
# exits 1 until cohort gate passes
```

Emergency override (audited):

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-paper-v1.1 \
  --force-cohort-gate "Manual override: demo deadline"
```

## 6. After gate passes → full paper-v1.1 repro

Only when `cohort_validation_report.json` shows `passed: true`:

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-paper-v1.1
uv run agent-query repro verify-tables --manifest releases/paper-v1.1/manifest.yaml --input reports/repro-paper-v1.1
uv run agent-query repro report --input reports/repro-paper-v1.1 --manifest releases/paper-v1.1/manifest.yaml
```

## Success checklist

- [ ] Investigation pack covers all tier-1 items with EDGAR links or documented omissions
- [ ] Auto-suggest taxonomy ≥70% agreement on 20-item audit sample
- [ ] Failure-mode regression suite green
- [ ] Cohort validate: ≥25% reduction in strong-retrieval zero-outcome vs paper-v1.0 baseline
- [ ] Cohort validate completes in <2h on operator hardware
- [ ] Full repro run-all unblocked only after cohort gate pass

## Related docs

- `specs/019-agent-failure-investigation/spec.md`
- `specs/018-eval-dataset-quality/quickstart.md`
- `docs/research-reproduction.md`
- `docs/eval-dataset-quality.md`
