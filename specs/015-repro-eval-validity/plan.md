# Implementation Plan: Reproduction Evaluation Validity & Stratified Ablations

**Branch**: `015-repro-eval-validity` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-repro-eval-validity/spec.md`

## Summary

Harden paper-v1.0 reproduction evaluation after discovering inverted outcome metrics, 500+ noisy per-item report warnings, and misleading pooled ablation tables. P0 scoring fixes (trajectory hydration, abstention penalty, GT-aware judge criteria, export-tables item context) are merged on `main` and verified only. This feature delivers P1–P3: wire structural audit metrics and document re-judge workflow; aggregate investigation notes in the 014 report; add evidence-stratum exports (`by_evidence_source.csv`, `variant_delta_by_source.csv`) and a stratified report section with manifest ablation guidance.

## Technical Context

**Language/Version**: Python 3.12+ (existing repo runtime)

**Primary Dependencies**: Typer CLI, Pydantic models (`models/reproduction.py`, `models/evaluation.py`), existing 012 export pipeline (`evaluation/reproduction/export.py`), 013 deferred judge (`judge_batch.py`), 014 report stack (`report_loader.py`, `report_render.py`), custom-judge bundle loader, `structural.py` (012 metrics, currently unwired)

**Storage**:
- Input: `reports/repro-{tag}/` checkpoints (`repro_run.json`, `{variant}/results.json`, `tables/*.csv`)
- Custom-judge bundle: `data/benchmarks/custom-judge/v1.0.0/` (item labels, relevance chunk ids)
- Output: updated `tables/` CSVs, `report.html`, enriched `repro_run.json` structural fields

**Testing**: pytest unit tests for stratum assignment, abstention rate, structural aggregation, judge resume gate, aggregated anomalies; integration smoke on `paper-smoke` or fixture bundle; acceptance check against `paper-v1.0` re-score (SC-001)

**Target Platform**: Local CLI + static HTML browser (offline)

**Project Type**: Single-project Python CLI extension under `src/evaluation/reproduction/`

**Performance Goals**:
- Re-score + re-export + report regeneration in < 30 minutes active operator time (SC-007; excludes judge API queue)
- Report investigation section ≤ 25 top-level notes (SC-004)

**Constraints**:
- No full agent re-run (1000 queries) unless operator chooses
- No changes to walker or xbrl-only retrieval behavior
- Stratification is reporting-only; all variants still run full dev split
- `variant_delta.csv` schema unchanged (pooled deltas only)

**Scale/Scope**:
- 5 standard variants × 200 dev items (paper-v1.0)
- Strata: html, xbrl, mixed, unknown (unknown excluded from stratified aggregates with audit count)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Abstention penalized when GT expects answer; synthesis must not invent numbers absent from citations; stratum labels derived from relevance chunk ids only | **PASS** |
| **II. Structural Semantics Preservation** | Structural metrics use expected bindings/section paths from benchmark items; no parser changes | **PASS** |
| **III. Traceability** | Trajectory evidence hydrated before judge; citation↔trajectory consistency enforced on write; structural audit from trajectory accessions/paths | **PASS** |
| **IV. Separation of Concerns** | Changes confined to evaluation/reproduction layer + report consumer; no retrieval behavior changes | **PASS** |
| **V. Code Health & Environment Stability** | Typed models at export/report boundaries; uv/lockfile unchanged | **PASS** |
| **VI. Rigorous Agent Evaluation** | Headline metrics, abstention rate, stratum tables, structural audit support paper claims; SC-001 strict ordering enforced | **PASS** |

**Post-design re-check**: Phase 1 contracts extend 012 export and 014 report schemas without cross-layer imports. Stratum assignment is read-only over custom-judge labels.

## Project Structure

### Documentation (this feature)

```text
specs/015-repro-eval-validity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── re-judge-workflow.md
│   ├── stratum-export.md
│   └── structural-metrics.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── evaluation/
│   ├── judges/
│   │   └── outcome_scoring.py          # VERIFY P0 (main)
│   └── reproduction/
│       ├── structural.py               # EXISTING: wire into runner
│       ├── stratum.py                  # NEW: primary_evidence_source assignment
│       ├── export.py                   # EXTEND: by_evidence_source, variant_delta_by_source
│       ├── judge_batch.py              # EXTEND: v2 resume skip gate
│       ├── runner.py                   # EXTEND: structural_metrics population
│       ├── report_models.py            # EXTEND: AggregatedInvestigationNote, stratum tables
│       ├── report_render.py            # EXTEND: aggregate anomalies, stratum section
│       └── report_loader.py            # EXTEND: load new CSV tables
├── tracing/
│   └── trajectory_export.py            # VERIFY P0 normalize (main)
└── cli/commands/
    └── repro.py                        # EXTEND: docs flags if needed

releases/paper-v1.0/
└── manifest.yaml                       # EXTEND: ablation guidance per stratum

docs/
└── research-reproduction.md            # EXTEND: re-judge workflow

tests/
├── unit/
│   ├── test_stratum.py                 # NEW
│   ├── test_structural_runner.py       # NEW
│   ├── test_repro_report_aggregated_notes.py  # NEW
│   └── test_outcome_scoring.py         # VERIFY P0
└── integration/
    └── test_stratum_export_smoke.py    # NEW
```

**Structure Decision**: Single-project extension within existing evaluation/reproduction package. Reuses 014 report template with new sections; no new service boundary.

## Complexity Tracking

No constitution violations requiring exceptions.

## Phase 0: Research

Completed in [research.md](./research.md):
- Evidence stratum classification rule (chunk id heuristics aligned with walker)
- Re-judge resume gate (judge version ≥ v2 + non-empty trajectory evidence)
- Structural metric extraction from trajectory snapshots
- Investigation note aggregation patterns
- Stratified export schema and low-n stratum handling

## Phase 1: Design

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Re-judge workflow | [contracts/re-judge-workflow.md](./contracts/re-judge-workflow.md) |
| Stratum export | [contracts/stratum-export.md](./contracts/stratum-export.md) |
| Structural metrics | [contracts/structural-metrics.md](./contracts/structural-metrics.md) |
| Operator quickstart | [quickstart.md](./quickstart.md) |

## Implementation phases (for /speckit-tasks)

### Phase A — P0 verification (no re-implementation)

1. Confirm `normalize_trajectory_state`, `compute_outcome_scores`, export `load_item_contexts` on `main`
2. Add acceptance test or documented checklist for SC-001 on re-scored `paper-v1.0`

### Phase B — P1 evaluation validity and structural audit

1. Add `stratum.py` with `assign_primary_evidence_source(relevant_chunk_ids)` (used later; can land in P1 for shared tests)
2. Add trajectory extraction helper: `used_accessions_by_item`, `visited_paths_by_item` from `trajectory_snapshot`
3. Wire `aggregate_structural_metrics` into `ReproRunner` finalization for all five variants → `variant_runs[].structural_metrics`
4. Extend `judge_batch._pending_results` with v2 resume skip per [re-judge-workflow.md](./contracts/re-judge-workflow.md)
5. Document re-judge workflow in `quickstart.md` and `docs/research-reproduction.md`
6. Enforce trajectory↔citation consistency on results write (runner or export guard)

### Phase C — P2 report investigation UX

1. Replace per-item `detect_run_anomalies` loops with `aggregate_investigation_notes()` → `AggregatedInvestigationNote[]`
2. Encode expected ablation patterns (no-walker/xbrl-only zero citations) as single info summaries
3. Gate "outcome exceeds graph-full" on retrieval overlap or non-zero citations (FR-010)
4. Render expandable notes with up to 5 example item ids; cap top-level notes at 25

### Phase D — P3 stratified ablation reporting

1. Extend `export.py` with `by_evidence_source.csv` and `variant_delta_by_source.csv`
2. Compute `abstention_rate` per variant/stratum during export
3. Extend `report_models.PaperTableId`, loader, render for stratified section
4. Update `releases/paper-v1.0/manifest.yaml` with valid comparison guidance per stratum
5. Integration test: strata item counts sum to eligible dev items (SC-005)

## Phase 2

Task breakdown and sequencing will be generated by `/speckit-tasks`.
