# Quickstart: Fair Reproduction Outcome Scoring (016)

**Feature**: 016-fair-outcome-scoring | **Date**: 2026-06-07

## Prerequisites

- Branch `016-fair-outcome-scoring` with implementation merged or in progress
- Existing `reports/repro-paper-v1.0/` agent checkpoints (optional reuse)
- Judge API credentials
- Bundle v1.1.0 published at `data/benchmarks/custom-judge/v1.1.0/`

## 1. Publish bundle v1.1.0

```bash
# After migration script / extend workflow produces draft
uv run agent-query benchmark publish \
  --draft data/benchmarks/custom-judge/drafts/v1.1.0 \
  --version 1.1.0
```

Verify `CHANGELOG.md` and `feasibility_report.json` show zero blocked comparison items.

Update release manifest to point at v1.1.0.

## 2. Selective agent re-run (changed items only)

For items flagged `requires_agent_rerun: true` in CHANGELOG:

```bash
uv run agent-query repro run \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variants graph-full,flat-chunk \
  --resume
```

Use item filters when CLI supports `--item-ids` from changelog list.

## 3. Full v3 re-judge

All variants need v3 verdicts with complete criteria:

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --force-rescore
```

Resume without `--force-rescore` skips only v3-complete items.

## 4. Export and report

```bash
uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

## 5. Verify success criteria

### SC-001 (target, not release block)

`tables/headline.csv`:

- `graph-full` outcome_accuracy > `ablation-no-walker`, `ablation-xbrl-only`
- `graph-full` MRR/nDCG > `flat-chunk`

If graph-full outcome ≤ flat-chunk on HTML stratum, check report for `OUTCOME_ORDERING_REGRESSION` note.

### SC-002

No answer-GT item uses synthesis_grounding as outcome_score (unit test + spot-check `results.json`).

### SC-003

flat-chunk verdicts lack trajectory criteria; include `answer_quality`.

### SC-004

`rubric_alignment` > 0 for graph-full after v3 re-judge (was 0 from incomplete v2 resume).

### SC-005

Report shows outcome-by-profile and outcome-by-stratum above pooled headline.

### SC-006

`feasibility_report.json` shows zero infeasible comparison items at publish.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| outcome_accuracy still flat-chunk > graph-full | Confirm `--force-rescore`; check value_alignment populated |
| rubric_alignment = 0 | Incomplete criteria; verify judge_version v3 |
| High synthesis on flat-chunk dumps | Confirm anti-dump rubric in judge config deployed |
