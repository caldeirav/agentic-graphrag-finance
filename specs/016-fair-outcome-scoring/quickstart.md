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

For items flagged `requires_agent_rerun: true` in `CHANGELOG.md` (typically `rubric_route` or `bindings` fixes):

1. List item ids: `grep 'requires_agent_rerun: true' -B3 data/benchmarks/custom-judge/v1.1.0/CHANGELOG.md`
2. Re-run agents only for those items on affected variants (`graph-full`, `flat-chunk`, ablations as needed):

```bash
uv run agent-query repro run \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variants graph-full,flat-chunk \
  --resume
```

**Unchanged items** keep existing checkpoints — do not delete `results.json` for items absent from CHANGELOG. **All items** still need v3 re-judge (step 3) even when agent checkpoints are reused.

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
| outcome_accuracy ~0.14 after v3 re-score | Expected on v1.1.0 until retrieval + graded VA; follow [v1.2.0 migration checklist](checklists/v1.2.0-migration.md) |

## Follow-on: bundle v1.2.0 (outcome calibration)

To raise outcome_accuracy materially while keeping VA-only policy, use the phased checklist:

**[checklists/v1.2.0-migration.md](checklists/v1.2.0-migration.md)** — Phases A (dataset) → B (agent) → C (judge) → D (paper repro).
