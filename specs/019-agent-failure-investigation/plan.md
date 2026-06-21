# Implementation Plan: Agent Failure Investigation and Remediation

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-agent-failure-investigation/spec.md`

## Summary

Extend the evaluation layer with a **unified failure-investigation workflow** for tier-1 agent failures (strong retrieval, zero outcome): merge repro results, draft GT, annotations, and materialization audit into a static HTML+CSV pack embedded in the 014 repro report; auto-suggest engineering failure taxonomy with mapping to 018 human classes; add **cohort debug** (re-run by default, replay optional) with structured trace summaries; implement **targeted retrieval fixes** (macro binding, numeric XBRL synthesis, template-dump reduction) with a failure-mode regression suite; and gate **paper-v1.1 full repro** behind a frozen **84-item tier-1 cohort** validation (hard block + `--force` audit override).

## Technical Context

**Language/Version**: Python 3.12+ (existing repo)

**Primary Dependencies**: Typer (`repro.py`, `benchmark_dataset.py`), Pydantic (`models/evaluation.py`, `models/benchmark_generation.py`), reproduction (`evaluation/reproduction/`: `report_render.py`, `report_loader.py`, `runner.py`, `smoke_gate.py`), generation review (`evaluation/generation/review/`), retrieval (`retrieval/synthesis.py`, `retrieval/macro/`, orchestration trace payloads), console trace (`tracing/console_trace/`), MLflow trajectory export (`tracing/`, `evaluation/reproduction/trajectory_export.py`)

**Storage**:
- Repro input: `reports/repro-paper-v1.0/` (baseline) and post-fix cohort runs under `reports/repro-cohort-*`
- Draft bundle: `data/benchmarks/custom-judge/drafts/quality-v2.0.1/`
- Frozen cohort: `tier1_cohort.json` in draft bundle (derived from `review_queue.json`)
- Investigation artifacts: `failure_investigation.html`, `failure_investigation.csv`, `cohort_validation_report.json`, `cohort_debug/` per-item summaries
- Target release: `releases/paper-v1.1/` (cohort gate thresholds in manifest)

**Testing**: pytest unit (taxonomy rules, EDGAR URL builder, materialization audit diff, gate logic); integration (export pack from fixture repro, cohort debug 5-item smoke, gate block on failing thresholds); contract (evaluation import boundaries); failure-mode regression module per remediation cluster

**Target Platform**: Local CLI + static HTML (offline)

**Project Type**: Single-project Python extension under `src/evaluation/reproduction/investigation/` and targeted `src/retrieval/` fixes

**Performance Goals**:
- Failure-investigation pack export for 84 tier-1 items < 30s
- Cohort validation (84 items, graph-full, agent+judge) < 2h on documented operator hardware
- Cohort debug replay mode for 84 items < 60s (no agent re-exec)

**Constraints**:
- paper-v1.0 and v2.0.0 immutable; cohort baseline snapshot pinned
- Repro batch runs keep `trace_level: quiet`; cohort debug uses `trace_level: normal` + JSONL
- Dual taxonomy: engineering codes vs 018 human classes (clarification)
- Graph context: link-first; inline only when pre-rendered bundle data exists
- No new judge model; no MRR/nDCG definition changes

**Scale/Scope**:
- ~84 tier-1 items (full queue as frozen cohort)
- 3 remediation clusters + guardrail regression cases
- Extends 014 report drill-down; extends 018 review CLI inputs
- Full 200×5 repro explicitly out of scope until cohort gate passes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Investigation pack surfaces EDGAR links and corpus excerpts; remediations strengthen XBRL deterministic synthesis; no ungrounded numeric answers in regression fixtures | **PASS** |
| **II. Structural Semantics Preservation** | Materialization audit compares expected section paths to visited nodes; no flat-string corpus regen | **PASS** |
| **III. Traceability** | Cohort debug emits structured summaries from console trace + MLflow trajectory; repro quiet default preserved for full runs | **PASS** |
| **IV. Separation of Concerns** | Investigation in `evaluation/reproduction/investigation/`; retrieval fixes in `retrieval/`; evaluation reads trajectories via existing contracts; no ingestion imports in generation | **PASS** |
| **V. Code Health & Environment Stability** | Typed Pydantic models for investigation row, cohort file, validation report; uv lockfile | **PASS** |
| **VI. Rigorous Agent Evaluation** | Cohort gate before paper-v1.1; failure-mode regression suite; external judge unchanged; modular tier-1 cohort file | **PASS** |

**Post-design re-check**: Contracts define evaluation-layer artifacts and CLI surfaces only. Retrieval remediations are scoped agent-path fixes with regression tests. No production ask-path blocking judge. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/019-agent-failure-investigation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── failure-investigation-pack.md
│   ├── taxonomy-suggestion.md
│   ├── cohort-debug-cli.md
│   ├── cohort-gate.md
│   ├── edgar-filing-links.md
│   └── failure-mode-regression.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── evaluation/
│   ├── reproduction/
│   │   ├── investigation/              # NEW package
│   │   │   ├── pack.py                 # HTML+CSV failure investigation export
│   │   │   ├── taxonomy.py             # engineering failure class suggestion
│   │   │   ├── materialization_audit.py
│   │   │   ├── edgar_links.py          # accession → EDGAR filing URL
│   │   │   ├── graph_context.py        # link-first subgraph panel data
│   │   │   ├── cohort.py               # freeze tier1_cohort.json from queue
│   │   │   ├── cohort_debug.py         # re-run / replay debug runner
│   │   │   └── cohort_gate.py          # validate + block run-all
│   │   ├── report_render.py            # EXTEND: drill-down investigation fields
│   │   ├── report_models.py            # EXTEND: FailureInvestigationFields
│   │   ├── runner.py                   # EXTEND: progress line fields; gate hook
│   │   └── smoke_gate.py               # REUSE: max_mrr_ok_va_zero in cohort report
│   └── generation/review/
│       └── quality_summary.py          # EXTEND: engineering taxonomy rollup
├── retrieval/
│   ├── macro/                          # EXTEND: form-type / period binding fixes
│   └── synthesis.py                    # EXTEND: numeric XBRL coverage; template-dump guard
├── models/
│   └── investigation.py                # NEW: Pydantic models
└── cli/commands/
    ├── repro.py                        # EXTEND: cohort-debug, cohort-validate, run-all gate
    └── benchmark_dataset.py            # EXTEND: review export-investigation

releases/paper-v1.1/
└── manifest.yaml                       # EXTEND: cohort_gate_thresholds section

tests/
├── unit/
│   ├── test_failure_taxonomy.py
│   ├── test_edgar_links.py
│   ├── test_materialization_audit.py
│   └── test_cohort_gate.py
├── integration/
│   ├── test_failure_investigation_pack.py
│   ├── test_cohort_debug_smoke.py
│   └── test_failure_mode_regression.py
└── regression/
    └── failure_modes/                  # NEW: tier-1 pattern fixtures per cluster
```

**Structure Decision**: Single-project extension. Investigation logic lives under `evaluation/reproduction/investigation/` (evaluation layer, read-only over repro + bundle). Agent remediations stay in `retrieval/` with dedicated regression fixtures.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Phases (for tasks.md)

### Phase A — Investigation data (P1)

1. `investigation/edgar_links.py` + `materialization_audit.py`
2. `investigation/taxonomy.py` + default mapping to 018 classes
3. `investigation/pack.py` HTML+CSV; wire `benchmark-dataset review export-investigation`
4. Extend `report_render.py` drill-down with shared field builder

### Phase B — Observability (P2)

5. `investigation/cohort_debug.py` (re-run default, `--replay`)
6. Structured per-item summary JSON + stdout progress enrichment in `runner.py`
7. `investigation/graph_context.py` link-first panel

### Phase C — Agent remediations (P2)

8. Macro binding fixes + regression cases
9. Synthesis numeric XBRL + template-dump guard + regression cases
10. Comparison narrative synthesis improvements + regression cases

### Phase D — Cohort gate (P1)

11. `investigation/cohort.py` freeze from `review_queue.json`
12. `investigation/cohort_gate.py` + `repro cohort-validate`
13. Hard block in `repro run-all` for paper-v1.1 + `--force` audit
14. `cohort_gate_thresholds` in paper-v1.1 manifest

## Dependencies

- **018-eval-dataset-quality** (shipped): review queue, annotations, quality summary
- **014-repro-results-viewer** (shipped): report HTML template and drill-down
- **007-ask-console-trace** (shipped): trace registry for cohort debug summaries
- **008-autonomous-macro-routing**: macro binding remediation target
- **paper-v1.1 manifest** (draft): cohort gate threshold configuration
