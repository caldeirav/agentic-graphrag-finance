# Re-Judge Workflow Contract (015)

**Feature**: 015-repro-eval-validity | **Spec**: FR-001, FR-000, SC-001, SC-007

## Purpose

Re-score existing per-variant `results.json` checkpoints without re-running agents, then re-export paper tables and regenerate the investigation report.

## Prerequisites

- Completed reproduction output: `reports/repro-{tag}/`
- Custom-judge bundle path from release manifest (e.g. `data/benchmarks/custom-judge/v1.0.0`)
- P0 scoring code on `main` (trajectory hydration, abstention penalty, GT-aware criteria, export item context)
- Judge API credentials configured (Gemini per `configs/judges/gemini_2_5_pro.yaml`)

## Commands

```bash
# 1. Re-score all variants on dev split (idempotent resume)
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

# Optional: force re-score items already at judge v2
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --force-rescore

# 2. Re-export paper tables (includes stratum tables after P3)
uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

# 3. Regenerate HTML report
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

## judge-batch behavior

| Input | Behavior |
|-------|----------|
| `--manifest` | Resolves `custom_judge_bundle_path`, `eval_split` |
| `--input` | Root `reports/repro-{tag}/` with variant subdirs |
| `--variant` | Optional single variant filter |
| `--concurrency` | Parallel judge workers (default from manifest/config) |
| `--force-rescore` | Bypass v2 resume skip (NEW) |

### Pending item selection

An item is **pending** when:

1. `judge_status` is `pending` (defer-judge flow), OR
2. Pre-P0 score needs refresh: not skipped by resume gate below

An item is **skipped** (resume) when **all** hold:

1. `judge_verdict.judge_version` ≥ `v2`
2. After `normalize_trajectory_state`, `evidence_chunks` is non-empty
3. `--force-rescore` is not set

An item with empty trajectory evidence but non-empty `answer.citations` is **not skipped**; judge uses citation fallback.

### Outputs

- Updates `{variant}/results.json` atomically per variant
- Returns stats: `{judged, skipped, failed}`

## export-tables behavior

- Loads item context from custom-judge bundle (`load_item_contexts`)
- Writes `tables/headline.csv`, `by_profile.csv`, `variant_delta.csv`, `trajectory_audit.csv`
- After P3: also writes `by_evidence_source.csv`, `variant_delta_by_source.csv`

### Pending items

Follows 013 rules: pending judge items excluded from headline unless `--allow-pending-export`.

## Acceptance (SC-001)

After re-judge on `paper-v1.0`:

```
graph-full.outcome_accuracy > ablation-no-walker.outcome_accuracy
graph-full.outcome_accuracy > ablation-xbrl-only.outcome_accuracy
```

Strict ordering on full dev split; no tolerance band.

Ranking metrics unchanged expectation: `graph-full` MRR/nDCG >> `flat-chunk` >> abstaining ablations.

## Errors

| Condition | Result |
|-----------|--------|
| Missing `results.json` for variant | Skip variant, log warning |
| Item not in judge split | `judge_status=not_evaluable` |
| Judge API failure | Increment `failed`, log item_id |
| Missing bundle path | Hard error with manifest path hint |
