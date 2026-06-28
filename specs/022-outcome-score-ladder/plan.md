# Implementation Plan: Outcome Score Ladder (022)

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

## Summary

Raise `outcome_score` on the 26-item XBRL cohort through **five gated phases**: ratio pair pipeline (A), point-fact catalog (B), benchmark/slice expansion (C), HTML table fallback (D), segment graph (E). Each phase ships code + unit/fixture tests + **cohort re-run gate** before the next phase starts.

## Technical Context

**Language**: Python 3.12+  
**Depends on**: 021 skills (`temporal_scope`, `xbrl_fact_catalog`, `metric_intent`, `numeric_computation`, `xbrl_concept_guards`)  
**Validation**: `uv run pytest` per phase; operator cohort-debug + judge-batch  
**Outcome metric**: `outcome_score` = `value_alignment` (answer-GT items); partial VA ≥ 0.5 counts

## Architecture (live synthesis)

```text
macro bind (021/022 temporal rebind)
  → build_xbrl_fact_catalog (guards + period)
  → classify_metric_intent
  → [A] resolve_ratio_pair OR resolve point facts
  → [D] html_table_fallback if catalog empty
  → compute_numeric_answer (percent for ratios)
  → structured render OR abstain
```

## Project Structure

```text
specs/022-outcome-score-ladder/
├── spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md
├── contracts/
├── fixtures/cohort_phase_targets.json
└── checklists/requirements.md

src/retrieval/skills/
├── ratio_pair_resolution.py      # NEW phase A
├── xbrl_concept_guards.py          # EXTEND phase A
├── point_fact_selection.py         # NEW phase B
├── html_table_fallback.py          # NEW phase D
├── xbrl_fact_catalog.py            # MODIFY A,B
├── numeric_computation.py          # MODIFY A
└── metric_intent.py                # MODIFY A

src/evaluation/reproduction/
├── snapshot_loader.py              # MODIFY phase C (slice expansion)
└── runner.py                       # MODIFY phase C (expanded pre_bound)

src/parsing/ or src/graph/          # MODIFY phase E (segment dimension)

tests/
├── unit/test_ratio_pair_resolution.py
├── unit/test_point_fact_selection.py
├── unit/test_slice_expansion.py
├── unit/test_html_table_fallback.py
├── fixtures/ratio_pairs/
├── fixtures/point_facts/
└── regression/cohort_gates/test_phase_a_gate.py  # mock/smoke thresholds
```

## Execution Order

| Phase | Story | Deliverable | Cohort gate |
|-------|-------|-------------|-------------|
| **A** | US-A Ratio | pair resolution, percent output, guards | ≥2 outcome>0 |
| **B** | US-B Point | point selector, CAT binding | ≥5 cumulative |
| **C** | US-C Slice | expand subgraph, binding audit | ≥7 cumulative |
| **D** | US-D HTML | table fallback skill | ≥8 cumulative |
| **E** | US-E Segment | graph segment dimension | ≥10 cumulative |

**Do not start phase N+1 until phase N cohort gate passes** (or operator documents waiver in `research.md`).

## Phase A detail (022b)

1. `RatioPairIntent` heuristics: margin, tax rate, dividend payout
2. `resolve_ratio_pair(catalog, intent)` → two entries or abstain
3. `compute_numeric_answer`: ratio branch outputs `%` only
4. Extend guards: reject statutory tax, single-fact ratio answers
5. Tests: fixtures for 0548/0667 GT percentages; regression no `$ billion` rate answers

## Phase B detail

1. `select_point_fact(catalog, query)` — annual primary concept priority
2. Issuer routing: map benchmark accession → ticker; CAT path for 0495
3. Scale normalization vs GT (raw units vs millions)
4. Tests: 0436 equity, 0495 cash fixtures from Dec-2025 10-K excerpts

## Phase C detail

1. `expand_slice_accessions(item, snapshot, intent)` in snapshot_loader
2. Include prior-year 10-K when `comparison_mode=yoy` or delta intent
3. Optional: `data/benchmarks/.../binding_rebound_changelog.jsonl`
4. Tests: 0600 no macro fail when FY2024 in corpus

## Phase D detail

1. `extract_from_html_tables(evidence, query, intent)` — targeted row/column
2. Wire in synthesis after empty catalog; before LLM
3. Chunk-dump guard must still pass
4. Tests: equity rollforward HTML fixture

## Phase E detail

1. Segment dimension in graph build / XBRL indexing
2. Catalog `segment_dimension` filter
3. Tests: 0428 segment fixture (skip if graph asset unavailable in CI)

## Validation commands

See [quickstart.md](./quickstart.md).

## Complexity Tracking

| Violation | Why | Alternative |
|-----------|-----|-------------|
| Benchmark accession edits | MRR + audit alignment | Agent-only rebind (insufficient for 0600) |
| HTML fallback | XBRL gaps on equity | LLM-only (failed VA) |
| Segment graph work | 0428 GT requires dimension | Defer phase E |

## Constitution

Principle VII: skills + schemas; Python math; no new live deterministic keyword handlers.
