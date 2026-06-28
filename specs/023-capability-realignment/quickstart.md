# Quickstart: Capability Realignment (023)

## Prerequisites

- 022-E baseline: `reports/cohort-022-phase-e` (0/26)
- Latest validation baseline: `reports/cohort-023-m4b` (0/26 outcome_gt0; 0548 abstains)
- `export OFFLINE_BENCHMARK=1`
- Live LLM + judge keys configured (same as cohort-debug)

## Cohort fixture

`specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json`

## Milestone workflow

### M1 — Single path + telemetry

```bash
uv run pytest tests/unit/test_numeric_synthesis_policy.py \
  tests/regression/failure_modes/test_no_numeric_llm_fallback.py \
  tests/unit/test_repro_trajectory_snapshot.py -q

uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-023-m1 \
  --no-resume

uv run agent-query repro judge-batch \
  --input reports/cohort-023-m1 \
  --manifest releases/paper-v1.1/manifest.yaml \
  --variant graph-full \
  --item-ids-file specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --force-rescore

uv run python specs/023-capability-realignment/scripts/audit_cohort_synthesis_paths.py \
  --report reports/cohort-023-m1
```

**Pass**: 0 numeric items classified `live_llm`/`structured_llm`; 26/26 `synthesis_path` set.

### M2 — LLM pairs + enrichment

```bash
uv run pytest tests/unit/test_xbrl_fact_resolution.py \
  tests/unit/test_numeric_evidence_enrichment.py -q

# cohort → reports/cohort-023-m2
uv run python specs/022-outcome-score-ladder/scripts/check_phase_gate.py \
  --report reports/cohort-023-m2 --phase A
```

**Pass**: ≥2/26 outcome_gt0.

### M3 — Post-validation + heuristic retirement

```bash
uv run pytest tests/unit/test_xbrl_resolution_validate.py \
  tests/regression/failure_modes/test_no_live_heuristic_imports.py -q

# cohort → reports/cohort-023-m3
uv run python specs/022-outcome-score-ladder/scripts/check_phase_gate.py \
  --report reports/cohort-023-m3 --phase C
```

**Pass**: floor ≥5 cumulative outcome_gt0 (not yet met).

### M3b — Filing-level XBRL catalog index

```bash
uv run pytest tests/unit/test_xbrl_filing_index_catalog.py \
  tests/regression/failure_modes/test_no_live_heuristic_imports.py -q

# cohort → reports/cohort-023-m3b
```

**Shipped**: `collect_filing_xbrl_chunks`, live `point_fact_selection` / `html_table_fallback` removed from synthesis.

### M4 — Taxonomy linkbase index (catalog v3)

```bash
uv run pytest tests/unit/test_xbrl_taxonomy_index.py \
  tests/unit/test_xbrl_taxonomy_catalog.py \
  tests/unit/test_xbrl_resolution_validate.py -q

# cohort → reports/cohort-023-m4
```

**Shipped**: `xbrl_taxonomy_index.py` (label/presentation/calculation), `ParsedDocument.xbrl_taxonomy_index`, graph node props, catalog schema v3, package fallback for existing snapshots.

### M4b — Role-aware ratio validation + fiscal period guard

```bash
uv run pytest tests/unit/test_ratio_entry_roles.py \
  tests/unit/test_xbrl_resolution_validate.py \
  tests/unit/test_temporal_scope.py \
  tests/unit/test_numeric_computation.py -q

uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-023-m4b \
  --no-resume

uv run python specs/023-capability-realignment/scripts/audit_cohort_synthesis_paths.py \
  --report reports/cohort-023-m4b

uv run python specs/022-outcome-score-ladder/scripts/check_phase_gate.py \
  --report reports/cohort-023-m4b --phase C
```

**Pass (partial)**: 0548 abstains instead of wrong pretax margin; SC-002 still **0/26** outcome_gt0.

## Path audit classes

| Class | Allowed after 023? |
|-------|-------------------|
| `computed_numeric` | Yes |
| `numeric_abstain` | Yes |
| `structured_llm` | No (numeric items) |
| `live_llm` | No (numeric items) |
| `macro_fail` | Tracked separately |

## Constitution review

Complete [checklists/constitution-vii.md](./checklists/constitution-vii.md) before merge.

## References

- [spec.md](./spec.md)
- [plan.md](./plan.md)
- [research.md](./research.md) — cohort ladder table
- `.specify/memory/constitution.md` Principle VII
- `specs/020-agent-capability-first/spec.md`
