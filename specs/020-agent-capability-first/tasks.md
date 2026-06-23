# Tasks: Agent Capability-First Numeric Synthesis

**Input**: Design documents from `/specs/020-agent-capability-first/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Create feature directory `specs/020-agent-capability-first/` with spec, plan, research, data-model, quickstart, contracts, checklists
- [x] T002 [P] Set `.specify/feature.json` to `020-agent-capability-first`

---

## Phase 2: Foundational

- [x] T003 Create `src/retrieval/skills/__init__.py` exporting public skill entry points
- [x] T004 [P] Add `StructuredAnswerPayload` and chunk-dump detector in `src/retrieval/skills/structured_answer.py` per contracts/structured-answer.schema.json

---

## Phase 3: User Story 1 - Structured Numeric Answers (P1)

**Goal**: Ban chunk dumps in live synthesis; structured JSON → prose.

- [x] T005 [US1] Implement `synthesize_structured_answer()` and `render_structured_answer()` in structured_answer.py
- [x] T006 [US1] Gate `_try_synthesize_*` handler loop in synthesis.py to `USE_MOCK_LLM=1` only
- [x] T007 [US1] Wire live synthesis path: structured → LLM fallback → abstain (no template dump)
- [x] T008 [US1] Add chunk-dump retry once when LLM returns dump pattern
- [x] T009 [P] [US1] Unit tests in `tests/unit/test_structured_answer.py`

**Checkpoint**: Live path never emits "Based on N evidence chunk(s)" in tests.

---

## Phase 4: User Story 2 - Temporal Binding (P1)

**Goal**: Macro planner and synthesis receive benchmark fiscal hints.

- [x] T010 [US2] Add `fiscal_period_labels_json` to AgentState and QueryService initial state
- [x] T011 [US2] Pass `fiscal_period_labels` from runner.py benchmark metadata
- [x] T012 [US2] Extend `plan_macro_binding()` prompt with temporal_anchor + fiscal_period_labels
- [x] T013 [US2] Pass hints from macro_router.py; include in structured synthesis system prompt
- [x] T014 [P] [US2] Unit test temporal hint propagation in `tests/unit/test_macro_temporal_hints.py`

**Checkpoint**: Planner prompt contains fiscal hint when metadata present.

---

## Phase 5: User Story 3 - XBRL Fact Resolution (P2)

**Goal**: LLM selects matching XBRL facts before synthesis.

- [x] T015 [US3] Implement `resolve_xbrl_facts()` in `src/retrieval/skills/xbrl_fact_resolution.py`
- [x] T016 [US3] Call resolution skill from synthesis when ≥2 XBRL evidence chunks
- [x] T017 [P] [US3] Unit tests with mocked LLM in `tests/unit/test_xbrl_fact_resolution.py`

**Checkpoint**: Resolution returns filtered evidence list and rationale string.

---

## Phase 6: User Story 4 - XBRL Cohort (P2)

**Goal**: Frozen 26-item cohort for cohort-debug.

- [x] T018 [US4] Add `data/benchmarks/custom-judge/drafts/quality-v2.0.1/xbrl_numeric_cohort.json`
- [x] T019 [US4] Document cohort-debug workflow in `specs/020-agent-capability-first/quickstart.md`
- [x] T020 [P] [US4] Regression test `tests/regression/failure_modes/test_no_template_dump_live.py`

**Checkpoint**: Cohort file validates 26 ids; quickstart commands documented.

---

## Phase 7: User Story 5 - Governance (P3)

**Goal**: Principle VII + Cursor rule.

- [x] T021 [US5] Add Principle VII to `.specify/memory/constitution.md`
- [x] T022 [US5] Create `.cursor/rules/agent-capability-first.mdc`
- [x] T023 [US5] Update `.cursor/rules/specify-rules.mdc` plan pointer to 020

**Checkpoint**: Constitution and rules reference capability-first ladder.

---

## Phase 8: Polish

- [x] T024 Run targeted pytest suite for all new tests
- [x] T025 Mark checklists/requirements.md complete

---

## Dependencies

```text
Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → US5 → Polish
US2 can start after T005 (structured_answer exists)
US3 depends on US1 structured path
```

## Parallel Opportunities

- T004, T009, T014, T017, T020 can run in parallel after their prerequisites
- US4 cohort JSON (T018) independent of US3 code
