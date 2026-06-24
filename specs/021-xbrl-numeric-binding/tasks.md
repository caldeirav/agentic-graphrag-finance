# Tasks: FY Binding, Concept-Aware XBRL, and Numeric Computation

**Input**: `/specs/021-xbrl-numeric-binding/`  
**Prerequisites**: 020 shipped; cohort fixture available  
**Format**: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Create `specs/021-xbrl-numeric-binding/` artifacts (spec, plan, tasks, research, data-model, quickstart, contracts, checklists)
- [x] T002 [P] Set `.specify/feature.json` to `021-xbrl-numeric-binding`

---

## Phase 2: Foundational

- [x] T003 [P] Add contract schemas under `specs/021-xbrl-numeric-binding/contracts/`
- [x] T004 Extend `AgentState` / trace events for `temporal_scope_intent` and `metric_intent` (optional JSON fields)

---

## Phase 3: User Story 1 — FY Filing Binding (P1) — **Step 1**

**Goal**: Bind FY 10-K when question/metadata specify fiscal year; fix quarterly cue hijack.

- [x] T005 [US1] Implement `infer_temporal_scope_intent()` in `src/retrieval/skills/temporal_scope.py` (query + fiscal_period_labels + temporal_anchor)
- [x] T006 [US1] Export from `src/retrieval/skills/__init__.py`
- [x] T007 [US1] Add `annual_fiscal_year_requested()` guard in `pairing.py` / `detect_quarterly_metric_cue` path so revenue questions with “fiscal year YYYY” do not force 10-Q
- [x] T008 [US1] Apply intent in `macro_router.py`: merge into proposal (`period_labels`, `anchor`, `quarterly_metric_cue=false`) before `validate_macro_binding`
- [x] T009 [US1] Add validator period-mismatch guard in `validator.py`: narrow to `pair_period_labels` or FY-matching 10-K when bound label ≠ target year
- [x] T010 [P] [US1] Unit tests `tests/unit/test_temporal_scope.py` (FY2025 annual, Q1 explicit, YoY comparison)
- [x] T011 [P] [US1] Integration test: macro_router binds 10-K for “fiscal year 2025 revenue” fixture snapshot

**Checkpoint**: Cohort-debug re-run shows `binding_miss` ≤10; FY2025 items list 10-K in `filing_set`.

---

## Phase 4: User Story 2 — Concept-Aware XBRL (P1) — **Step 2**

**Goal**: Structured fact catalog + concept/period pre-filter before LLM resolution.

- [x] T012 [US2] Implement `build_xbrl_fact_catalog()` in `src/retrieval/skills/xbrl_fact_catalog.py` (parse excerpt, concept_family, period_end, is_annual)
- [x] T013 [US2] Reuse `parsing/xbrl_facts.xbrl_concept_matches_query` for pre-filter; add segment hint when excerpt contains segment name
- [x] T014 [US2] Refactor `resolve_xbrl_facts()` to consume catalog entries; always run when ≥1 XBRL chunk (not only ≥2)
- [x] T015 [P] [US2] Unit tests `tests/unit/test_xbrl_fact_catalog.py` + extend `test_xbrl_fact_resolution.py`

**Checkpoint**: 0436/0495 resolution tests pick annual equity / cash for correct period in mocks.

---

## Phase 5: User Story 3 — Computed Metrics (P2) — **Step 3**

**Goal**: Metric typing + Python computation for delta/ratio/percent_change.

- [x] T016 [US3] Implement `classify_metric_intent()` in `src/retrieval/skills/metric_intent.py` (LLM JSON + heuristic fallback)
- [x] T017 [US3] Implement `compute_numeric_answer()` in `src/retrieval/skills/numeric_computation.py` (parse values, apply formula, unit normalization)
- [x] T018 [US3] Extend `StructuredAnswerPayload` + `structured-answer-v2.schema.json` with `metric_type`, `inputs`, `formula`, `computed_value`
- [x] T019 [US3] Wire synthesis live path: catalog → metric intent → resolve (multi-fact for delta/ratio) → compute → structured render
- [x] T020 [P] [US3] Fixtures under `tests/fixtures/xbrl_computation/` + `tests/unit/test_metric_intent.py`, `test_numeric_computation.py`

**Checkpoint**: YoY/delta/ratio fixture tests pass; cohort items 0536/0600/0667 non-abstaining in local smoke.

---

## Phase 6: User Story 4 — Remove Live Overrides (P2) — **Step 4**

**Goal**: No live `_correct_numeric_from_xbrl` injection.

- [x] T021 [US4] Gate `_correct_numeric_from_xbrl`, `_correct_revenue_denial` numeric substitution paths to `USE_MOCK_LLM=1` in `synthesis.py`
- [x] T022 [P] [US4] Regression `tests/regression/failure_modes/test_live_no_deterministic_numeric.py`

**Checkpoint**: Live synthesis never emits “Per XBRL … bound fiscal period” template phrasing.

---

## Phase 7: Polish & Cohort Gate

- [x] T023 Update `specs/021-xbrl-numeric-binding/quickstart.md` with cohort re-run + judge commands
- [x] T024 Run full unit/regression suite for 021
- [ ] T025 Cohort-debug re-run; record before/after table in `research.md` (VA, abstention, binding_miss)
- [x] T026 Update `.cursor/rules/specify-rules.mdc` plan pointer to 021 when implementation starts
- [x] T027 Mark `checklists/requirements.md` complete

---

## Dependencies

```text
Setup → Foundational → US1 (Step 1) → US2 (Step 2) → US3 (Step 3) → US4 (Step 4) → Polish
US2 depends on T005 (target year from temporal intent)
US3 depends on US2 catalog
US4 can parallel US3 after T019 wired
```

## Parallel Opportunities

- T010, T011 after T005
- T015 after T012
- T020 after T017
- T022 independent of T020
