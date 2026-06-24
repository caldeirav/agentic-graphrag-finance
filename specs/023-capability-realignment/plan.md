# Implementation Plan: Capability Realignment (023 · 022c)

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

## Summary

Realign numeric synthesis with **Principle VII**: retire 022 heuristic-primary paths, enforce a **single live numeric pipeline** (catalog → LLM resolution → Python compute → structured render/abstain), add **retrieval enrichment** for multi-fact metrics, fix **repro telemetry**, and re-gate the 26-item cohort.

## Technical Context

**Language**: Python 3.12+  
**Depends on**: 021 skills, 022 slice expansion (keep), cohort fixture  
**Removes from live path**: `ratio_pair_resolution`, `point_fact_selection`, `html_table_fallback` imports in synthesis  
**Extends**: `xbrl_fact_resolution`, `synthesis.py`, micro retrieval / evidence assembly, `QueryService`, `ReproRunner._score_graph_item`

## Target architecture

```text
macro bind (021/022)
  → [NEW] enrich_numeric_evidence (ratio/delta families)
  → build_xbrl_fact_catalog (period filter ONLY)
  → classify_metric_intent (LLM; heuristic hint in prompt)
  → resolve_xbrl_facts (LLM; 1 or 2 facts; forbidden concepts in prompt)
  → [NEW] validate_xbrl_resolution (post-guards)
  → compute_numeric_answer (Python only)
  → render structured OR numeric_abstain
  ✗ NO structured_llm / live_llm for numeric types
```

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I Grounding | PASS | Python math after LLM fact pick |
| II Structure | PASS | Catalog from parsed XBRL excerpts |
| III Traceability | PASS | Resolution rationale + synthesis_path |
| IV Separation | PASS | Skills in retrieval/; eval reads artifacts |
| V Typing | PASS | Pydantic + contracts |
| VI Evaluation | PASS | Cohort gates unchanged |
| VII Capability-first | **PASS after 023** | Heuristic routers retired live |

## Complexity Tracking

| Violation | Why needed | Rejected alternative | Sunset |
|-----------|------------|----------------------|--------|
| Post-resolution concept validator (deterministic) | Principle I — reject LLM bad picks | Pre-filter catalog (022; failed) | Keep as validator only |
| `heuristic_metric_intent` in repro slice | Offline expansion only | LLM in repro runner | Already scoped |
| Retrieval enrichment (deterministic concept family lookup) | Surface XBRL chunks LLM must choose among | Regex pair routing | Review after SC-002 |
| Block numeric LLM fallthrough | Prevent 0666-style narrative | Allow “helpful” LLM fallback | Permanent policy |

## Project Structure

```text
specs/023-capability-realignment/
├── spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md
├── contracts/
├── fixtures/retired_modules.json, cohort_path_audit_thresholds.json
└── checklists/requirements.md, constitution-vii.md

src/retrieval/
├── synthesis.py                    # MODIFY — single path, no fallthrough
├── skills/
│   ├── xbrl_fact_resolution.py     # MODIFY — pair prompts, validation hook
│   ├── xbrl_fact_catalog.py        # MODIFY — soften pre-guards live
│   ├── xbrl_resolution_validate.py # NEW — post-selection guards
│   ├── numeric_evidence_enrichment.py # NEW — retrieval complement
│   ├── ratio_pair_resolution.py    # DEPRECATE live (mock tests only)
│   ├── point_fact_selection.py     # DEPRECATE live
│   └── html_table_fallback.py      # DEPRECATE live
├── service.py                      # MODIFY — always export trajectory
└── orchestration/nodes/            # MODIFY — enrichment before synthesis

src/evaluation/reproduction/runner.py  # MODIFY — trajectory on BenchmarkResult

tests/
├── unit/test_numeric_synthesis_policy.py
├── unit/test_xbrl_resolution_validate.py
├── unit/test_numeric_evidence_enrichment.py
├── regression/failure_modes/test_no_numeric_llm_fallback.py
└── regression/failure_modes/test_no_live_heuristic_imports.py
```

## Milestones

| Milestone | Stories | Gate |
|-----------|---------|------|
| **M1** | US1, US5 | SC-003 path audit; SC-004 telemetry |
| **M2** | US2, US3 | SC-001 ≥2 outcome_gt0 |
| **M3** | US4, US6 | SC-002 ≥5; constitution checklist |
| **M4** | Carry 022-C macro | 0600 non-macro-fail (optional 023b) |

## Validation

See [quickstart.md](./quickstart.md).
