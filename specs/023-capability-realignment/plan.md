# Implementation Plan: Capability Realignment (023 · 022c)

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)

## Summary

Realign numeric synthesis with **Principle VII**: retire 022 heuristic-primary paths, enforce a **single live numeric pipeline** (filing-level catalog → taxonomy metadata → LLM resolution → post-validation → Python compute → structured render/abstain), add **retrieval enrichment** for multi-fact metrics, fix **repro telemetry**, and re-gate the 26-item cohort.

## Technical Context

**Language**: Python 3.12+  
**Depends on**: 021 skills, 022 slice expansion (keep), cohort fixture, Docling XBRL linkbases at parse  
**Removes from live path**: `ratio_pair_resolution`, `point_fact_selection`, `html_table_fallback` imports in synthesis  
**Extends**: `xbrl_taxonomy_index`, `xbrl_taxonomy_catalog` v3, `xbrl_graph_chunks`, `ratio_entry_roles`, `xbrl_fact_resolution`, `synthesis.py`, `docling_graph_mapper`, micro retrieval / evidence assembly, `QueryService`, `ReproRunner._score_graph_item`

## Target architecture

```text
macro bind (021/022)
  → enrich_numeric_evidence (ratio/delta families)
  → collect_filing_xbrl_chunks + merge evidence (M3b filing index)
  → build_taxonomy_catalog (period filter + linkbase labels/roles/calc; v3)
  → classify_metric_intent (LLM)
  → resolve_xbrl_facts (LLM; 1 or 2 facts; forbidden concepts in prompt)
  → validate_xbrl_resolution (post-guards; role-aware ratio pair assignment)
  → compute_numeric_answer (Python only; ratio pairs ordered by metric_roles)
  → render structured OR numeric_abstain
  ✗ NO structured_llm / live_llm for numeric types
  ✗ NO live ratio_pair / point_fact / html_table heuristics
```

Parse/index time (M4):

```text
find_taxonomy_dir → build_taxonomy_index (_lab/_pre/_cal)
  → ParsedDocument.xbrl_taxonomy_index
  → CHUNK_XBRL_FACT node properties (standard_label, metric_roles, calc_*)
  → runtime fallback: load_filing_taxonomy_from_packages when graph nodes lack props
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
│   ├── xbrl_taxonomy_catalog.py    # v2→v3 — linkbase metadata, filing index merge
│   ├── xbrl_graph_chunks.py        # filing-level XBRL index + taxonomy lookup
│   ├── xbrl_resolution_validate.py # post-selection guards; role-aware margin
│   ├── ratio_entry_roles.py        # NEW — assign num/den by metric_roles
│   ├── numeric_evidence_enrichment.py
│   ├── xbrl_resolution_validate.py
│   ├── ratio_pair_resolution.py    # DEPRECATE live (mock tests only)
│   ├── point_fact_selection.py     # DEPRECATE live
│   └── html_table_fallback.py      # DEPRECATE live
├── service.py                      # MODIFY — always export trajectory
└── orchestration/nodes/            # MODIFY — enrichment before synthesis

src/parsing/
├── xbrl_taxonomy_index.py          # NEW — label/presentation/calculation linkbases
└── docling_xbrl.py                 # attach taxonomy index at parse

src/graph/
└── docling_graph_mapper.py         # propagate taxonomy props to XBRL fact nodes

src/evaluation/reproduction/runner.py  # MODIFY — trajectory on BenchmarkResult

tests/
├── unit/test_numeric_synthesis_policy.py
├── unit/test_xbrl_resolution_validate.py
├── unit/test_xbrl_taxonomy_index.py
├── unit/test_xbrl_filing_index_catalog.py
├── unit/test_ratio_entry_roles.py
├── unit/test_numeric_evidence_enrichment.py
├── regression/failure_modes/test_no_numeric_llm_fallback.py
└── regression/failure_modes/test_no_live_heuristic_imports.py
```

## Milestones

| Milestone | Stories | Gate | Cohort dir | Result (graph-full) |
|-----------|---------|------|------------|---------------------|
| **M1** | US1, US5 | SC-003 path audit; SC-004 telemetry | `cohort-023-m1` | Telemetry fixed; path audit pending operator sign-off |
| **M2** | US2, US3 | SC-001 ≥2 outcome_gt0 | `cohort-023-m2` | **0/26** outcome_gt0 |
| **M3** | US4, US6 | SC-002 ≥5 | `cohort-023-m3` | **0/26**; post-validator active |
| **M3b** | US3 filing index | Retire live heuristics | `cohort-023-m3b` | **0/26**; 19 abstain / 6 computed |
| **M4** | Taxonomy index | Fix 0548-style pretax margin | `cohort-023-m4` | **0/26**; 0548 still computed wrong (137.55%) |
| **M4b** | Role-aware ratio + FY guard | Block bad margin computes | `cohort-023-m4b` | **0/26**; **0548 abstains**; 22 abstain / 3 computed |
| **M5** | Carry 022-C macro | 0600 non-macro-fail | — | Open |

## Validation

See [quickstart.md](./quickstart.md).
