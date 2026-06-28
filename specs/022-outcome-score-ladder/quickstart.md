# Quickstart: Outcome Score Ladder (022)

## Prerequisites

- 021 + informal 022 binding shipped on `019-agent-failure-investigation`
- `export OFFLINE_BENCHMARK=1`
- Baseline recorded: `reports/cohort-xbrl-022-debug`

## Cohort fixture

`specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json` (26 items)

Phase target items: `specs/022-outcome-score-ladder/fixtures/cohort_phase_targets.json`

## Per-phase workflow

### 1. Implement phase tasks (see tasks.md)

### 2. Unit + fixture tests

```bash
# Phase A
uv run pytest tests/unit/test_ratio_pair_resolution.py \
  tests/unit/test_xbrl_concept_guards.py \
  tests/unit/test_numeric_computation.py -q

# Phase B
uv run pytest tests/unit/test_point_fact_selection.py \
  tests/unit/test_xbrl_fact_catalog.py -q

# Phase C
uv run pytest tests/unit/test_slice_expansion.py \
  tests/unit/test_macro_fy_binding.py -q

# Phase D
uv run pytest tests/unit/test_html_table_fallback.py -q

# Phase E
uv run pytest tests/unit/test_segment_catalog.py -q
```

### 3. Cohort re-run (required — not replay)

```bash
PHASE=a  # or b, c, d, e
uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-022-phase-${PHASE} \
  --no-resume

uv run agent-query repro judge-batch \
  --input reports/cohort-022-phase-${PHASE} \
  --manifest releases/paper-v1.1/manifest.yaml \
  --variant graph-full \
  --item-ids-file specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --force-rescore
```

### 4. Gate check script

```bash
uv run python specs/022-outcome-score-ladder/scripts/check_phase_gate.py \
  --report reports/cohort-022-phase-a \
  --phase A
```

Records results to `specs/022-outcome-score-ladder/research.md` (operator).

## Phase gates (outcome_gt0 / 26)

| Phase | Floor | Stretch |
|-------|-------|---------|
| A | ≥2 | ≥4 |
| B | ≥5 | ≥8 |
| C | ≥7 | ≥10 |
| D | ≥8 | ≥11 |
| E | ≥10 | ≥15 (SC-001) |

## Target items by phase

| Phase | Primary item_ids |
|-------|------------------|
| A | 0548, 0667, 0666, 0592 |
| B | 0436, 0495, 0534, 0547 |
| C | 0600, 0536, 0667 |
| D | 0436, 0449, 0460 |
| E | 0428, (segment-2) |

## References

- [spec.md](./spec.md) — SC-A through SC-E
- [tasks.md](./tasks.md) — implementation checklist
- `docs/research-reproduction.md`
