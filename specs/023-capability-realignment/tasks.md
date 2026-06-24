# Tasks: Capability Realignment (023)

**Input**: `/specs/023-capability-realignment/`  
**Prerequisites**: 022 shipped (`8e802e7`); baseline `reports/cohort-022-phase-e`  
**Format**: `[ID] [P?] [Story] Description`

---

## Phase 0: Setup

- [x] T001 Create spec artifacts (spec, plan, tasks, research, data-model, quickstart, contracts, checklists, fixtures)
- [x] T002 [P] Set `.specify/feature.json` to `023-capability-realignment`
- [x] T003 [P] Update `.cursor/rules/specify-rules.mdc` plan pointer to 023

---

## Phase 1: User Story 1 — Single Live Numeric Path (P1)

**Gate**: SC-003 — 0 numeric items on live_llm/structured_llm; SC-004 — 26/26 synthesis_path

- [x] T004 [US1] Add `NumericSynthesisPolicy` / helper in `synthesis.py` — detect numeric metric types
- [x] T005 [US1] Refactor `_try_computed_numeric_synthesis` → returns result **or** explicit `numeric_abstain` dict (not `None` for numeric)
- [x] T006 [US1] Remove numeric fallthrough: skip `_try_structured_synthesis` and live LLM when policy blocks
- [x] T007 [US1] Tag abstain path `synthesis_path=numeric_abstain`
- [x] T008 [US1] Fix `QueryService.answer` — always attach `trajectory_snapshot` (defer and non-defer)
- [x] T009 [US1] Fix `ReproRunner._score_graph_item` — copy `trajectory_snapshot` + merge `synthesis_path` onto `BenchmarkResult`

### Tests

- [x] T010 [P] [US1] `tests/regression/failure_modes/test_no_numeric_llm_fallback.py` — mock synthesis order
- [x] T011 [P] [US1] `tests/unit/test_numeric_synthesis_policy.py`
- [x] T012 [P] [US1] `tests/unit/test_repro_trajectory_snapshot.py` — non-defer path has synthesis_path

### Cohort gate M1

- [ ] T013 [US1] Cohort re-run → `reports/cohort-023-m1` + judge-batch
- [ ] T014 [US1] Run path audit script (T015) — confirm SC-003/SC-004

---

## Phase 2: User Story 2 — LLM Pair Resolution (P1)

**Gate**: SC-001 — ≥2/26 outcome_gt0

- [x] T016 [US2] Extend `resolve_xbrl_facts_from_catalog` prompt: ratio requires 2 ids; forbidden concepts list from metric/query
- [x] T017 [US2] Remove live calls to `resolve_ratio_pair` / `ratio_pair_to_resolution` from synthesis and resolution
- [x] T018 [US2] Wire `periods_needed=2` resolution branch for ratio without regex pair module
- [x] T019 [US2] Ensure `compute_numeric_answer` ratio branch uses resolution ids only (delete duplicate regex path if redundant)

### Tests

- [x] T020 [P] [US2] Extend `tests/unit/test_xbrl_fact_resolution.py` — mock LLM returns two ids for margin
- [x] T021 [P] [US2] Extend `tests/unit/test_numeric_computation.py` — percent from two-fact resolution
- [x] T022 [P] [US2] Keep `tests/unit/test_ratio_pair_resolution.py` as mock-only regression or mark deprecated

### Cohort gate M2 (partial)

- [x] T023 [US2] Cohort re-run → `reports/cohort-023-m2` + judge-batch
- [ ] T024 [US2] `check_phase_gate.py` adapted thresholds — floor ≥2 outcome_gt0

---

## Phase 3: User Story 3 — Retrieval Enrichment (P1)

- [x] T025 [US3] Add `numeric_evidence_enrichment.py` — detect missing concept families for metric intent
- [x] T026 [US3] Wire enrichment before synthesis (graph micro or pre-synthesis node) using bound filing XBRL index
- [x] T027 [US3] Trace field `evidence_enrichment_json` on state
- [x] T028 [US3] Ratio targets: ensure revenue + income families present when available in snapshot

### Tests

- [x] T029 [P] [US3] `tests/unit/test_numeric_evidence_enrichment.py` — 0548 fixture adds revenue chunk
- [x] T030 [P] [US3] Integration smoke: catalog ≥2 ratio concepts for margin mock evidence

### Cohort gate M2 (full)

- [ ] T031 [US3] Cohort re-run → `reports/cohort-023-m2b` — target 0548/0667 non-abstain or VA>0

---

## Phase 4: User Story 4 — Post-Selection Validation (P2)

**Gate**: SC-002 — ≥5/26 outcome_gt0

- [x] T032 [US4] Add `xbrl_resolution_validate.py` — reject picks failing concept/period guards
- [x] T033 [US4] Soften `build_xbrl_fact_catalog` — `strict_concept=False` live; period filter remains
- [x] T034 [US4] Move guard calls from catalog loop to post-resolution validator
- [x] T035 [US4] Enrich resolution LLM prompt with forbidden patterns (statutory tax, EquityOther, Q1 interim)

### Tests

- [x] T036 [P] [US4] `tests/unit/test_xbrl_resolution_validate.py`
- [x] T037 [P] [US4] Update `test_xbrl_fact_catalog.py` — catalog includes guarded concepts; validator rejects

### Cohort gate M3

- [ ] T038 [US4] Cohort → `reports/cohort-023-m3` + judge-batch; floor ≥5

---

## Phase 5: User Story 6 — Heuristic Retirement (P2)

- [ ] T039 [US6] Remove live imports: `point_fact_selection`, `html_table_fallback` from synthesis
- [ ] T040 [US6] Mark modules deprecated in docstrings; keep for mock/CI if needed
- [ ] T041 [P] [US6] `tests/regression/failure_modes/test_no_live_heuristic_imports.py`
- [ ] T042 [US6] Update 022 research.md cross-link — superseded by 023

### Tests

- [ ] T043 [P] [US6] Complete `checklists/constitution-vii.md`

---

## Phase 6: Polish

- [ ] T044 [P] Add `scripts/audit_cohort_synthesis_paths.py` — SC-003 classifier
- [ ] T045 Update `specs/023-capability-realignment/checklists/requirements.md`
- [ ] T046 Record final metrics in `research.md`
- [ ] T047 Run pytest suite for 023 modules

---

## Dependencies

```text
T001–T003 → T004–T014 (M1) → T016–T024 (M2 LLM) → T025–T031 (M2 enrich) → T032–T038 (M3) → T039–T043 (retire)
```

## Validation summary

| Milestone | Tests | Cohort | Gate |
|-----------|-------|--------|------|
| M1 | policy, no fallback, telemetry | cohort-023-m1 | SC-003, SC-004 |
| M2 | resolution pair, enrichment | cohort-023-m2 | SC-001 ≥2 |
| M3 | post-validate | cohort-023-m3 | SC-002 ≥5 |
