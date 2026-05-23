---
description: "Task list for autonomous macro routing (008)"
---

# Tasks: Autonomous Macro Routing for Filing & Temporal Scope

**Input**: Design documents from `specs/008-autonomous-macro-routing/`

**Prerequisites**: `003-multi-filing-corpus`, `007-ask-console-trace` on branch; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit, contract, and integration tests per plan and spec independent-test criteria (validator determinism, trajectory schema, benchmark gates).

**Organization**: Foundational macro package blocks all stories; US1 is MVP (NL single-filing autonomous path); **US4 trajectory immediately after US1**; US2 is P1; US3/US5 are P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/retrieval/macro/`, `configs/macro_phrases.yaml`, `evaluation/metrics/macro_binding.py`, `data/benchmarks/finagentbench/macro_binding.jsonl`
- Extend: `src/retrieval/orchestration/nodes/macro_router.py`, `src/cli/corpus_pipeline.py`, `src/retrieval/service.py`, `src/tracing/mlflow_langgraph.py`, `src/retrieval/orchestration/trace_payloads.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Macro package scaffold, phrase catalog, test fixtures

- [x] T001 Create `src/retrieval/macro/__init__.py` and package exports per `plan.md`
- [x] T002 [P] Add `configs/macro_phrases.yaml` with anchors (latest_quarter, prior_quarter, latest_annual), comparison cues, and quarterly-metric tokens per `research.md` R3
- [x] T003 [P] Add `tests/fixtures/macro_validator/` with AAPL multi-filing manifest snapshot JSON per `contracts/macro-binding-validator.md`
- [x] T004 [P] Add `tests/fixtures/macro_planner/` with `USE_MOCK_LLM` JSON stubs per `contracts/macro-planner-llm.md`

**Checkpoint**: `uv run python -c "from retrieval.macro import models"` succeeds after T001

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed models, pairing rules, deterministic validator, CLI empty-scope handoff — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T005 [P] Implement `MacroBindingProposal`, `BindingValidationResult`, `MacroBindingRecord`, `MisalignmentCode` in `src/retrieval/macro/models.py` per `data-model.md`
- [x] T006a [P] Implement `detect_quarterly_metric_cue(query: str) -> bool` in `src/retrieval/macro/pairing.py` using `configs/macro_phrases.yaml` metric tokens; consumed by pairing YoY branch and validator
- [x] T006 Implement YoY/QoQ/single-anchor resolution in `src/retrieval/macro/pairing.py` per clarifications (YoY quarterly/annual, QoQ sequential), **branching on `quarterly_metric_cue` from T006a**
- [x] T007 [P] Add `tests/unit/test_macro_pairing.py` covering YoY (with/without metric cue), QoQ, latest/prior quarter against fixture manifest
- [x] T008 Implement `validate_macro_binding()` in `src/retrieval/macro/validator.py` per `contracts/macro-binding-validator.md`, including **fail-closed default**, **narrow-path downgrade** (clarification Q1), and misalignment codes used by FR-004/FR-010
- [x] T009 [P] Add `tests/unit/test_macro_validator.py` for approved, failed, narrowed statuses, and **≥10 misalignment scenarios** (SC-004 unit coverage; integration in T023)
- [x] T010 [P] Add `tests/unit/test_macro_validator_cli_conflict.py` for CLI precedence (FR-006)
- [x] T011 Update `bind_filings_for_query()` / `src/cli/corpus_pipeline.py` so empty `CorpusTemporalScope` does not pass full snapshot as `pre_bound_filings` per `research.md` R1
- [x] T012 Extend `QueryRequest` / graph initial state in `src/retrieval/service.py` to support deferred macro binding (`filing_set=[]`, `binding_deferred` metadata)

**Checkpoint**: `uv run pytest tests/unit/test_macro_pairing.py tests/unit/test_macro_validator.py -q` passes

---

## Phase 3: User Story 1 - Natural-Language Period Selection (Priority: P1) 🎯 MVP

**Goal**: Ask without `--period`/`--anchor` binds correct single 10-K or 10-Q from NL cues (latest quarter, prior quarter, annual report)

**Independent Test**: `USE_MOCK_LLM=1 uv run agent-query ask --ticker AAPL --trace normal --query "What was revenue in the prior quarter?"` binds one 10-Q; macro trace shows `validation_status=approved`

### Tests for User Story 1

- [x] T013 [P] [US1] Add integration test `tests/integration/test_ask_macro_nl_binding.py` for latest_quarter, prior_quarter, latest 10-K phrases per spec acceptance scenarios

### Implementation for User Story 1

- [x] T014 [P] [US1] Implement `plan_macro_binding()` LLM JSON proposal in `src/retrieval/macro/planner.py` per `contracts/macro-planner-llm.md`
- [x] T015 [US1] Refactor `macro_router()` in `src/retrieval/orchestration/nodes/macro_router.py` to: planner → validator → set `filing_set` / `macro_plan` or binding failure state
- [x] T016 [US1] Short-circuit `macro_llm_skipped` only when CLI pre-bound accessions present in `src/retrieval/orchestration/nodes/macro_router.py`
- [x] T017 [US1] Ensure meso/micro skipped when validator `failed` via graph conditional or early exit in `src/retrieval/service.py`

**Checkpoint**: US1 integration tests pass; qualitative NL queries bind single filing without `--period`

**Next (MVP)**: Proceed to **Phase 4 (US4)** before Phase 5 (US2). Do not defer T030–T031 past multi-filing work.

---

## Phase 4: User Story 4 - Durable Trajectory for Every Query (Priority: P1)

**Goal**: Every ask logs `macro_binding.json` and console macro trace with accessions, comparison mode, rationale (including pre-bound skip)

**Independent Test**: Smoke: one MLflow ask (T029). SC-003: batch audit ≥50 runs (T029a).

### Tests for User Story 4

- [x] T028 [P] [US4] Add contract test `tests/contract/test_macro_trajectory_schema.py` per `contracts/macro-trajectory.md`
- [x] T029 [P] [US4] Add integration test `tests/integration/test_ask_macro_trajectory.py` asserting `macro_binding.json` on **one** representative MLflow ask (smoke); **SC-003 batch coverage is T029a**
- [x] T029a [P] [US4] Add `tests/integration/test_macro_trajectory_batch.py`: loop over **≥50** stubbed/mock asks (or replay `macro_binding.jsonl` IDs with `USE_MOCK_LLM=1`), assert every run’s `macro_binding.json` / trajectory includes `selected_accessions`, `comparison_mode`, `rationale` per `contracts/macro-trajectory.md` (SC-003)

### Implementation for User Story 4

- [x] T030 [US4] Implement `log_macro_binding()` in `src/tracing/mlflow_langgraph.py` and call from `src/retrieval/service.py`
- [x] T031 [US4] Extend `build_macro_router_trace_payload()` in `src/retrieval/orchestration/trace_payloads.py` with proposal, validation, binding_source
- [x] T032 [US4] Update macro renderer in `src/tracing/console_trace/registry.py` for validation_status and failure_codes
- [x] T033 [US4] Include `macro_binding` in `build_trajectory_from_state()` / `TrajectoryRecord` in `src/tracing/mlflow_langgraph.py`
- [x] T034 [US4] Record-only validator pass for CLI pre-bound path in `src/retrieval/orchestration/nodes/macro_router.py`

**Checkpoint**: quickstart §5 passes; trajectory fields present for CLI and autonomous paths

---

## Phase 5: User Story 2 - Multi-Filing Comparison Scope (Priority: P1)

**Goal**: YoY and QoQ questions bind two+ accessions with correct `comparison_mode` recorded

**Independent Test**: YoY revenue query selects latest 10-Q + prior-year same fiscal quarter; QoQ selects latest + prior sequential 10-Q

### Tests for User Story 2

- [x] T018 [P] [US2] Add `tests/unit/test_macro_validator_yoy_qoq.py` for pairing materialization and fail-closed missing partner
- [x] T019 [P] [US2] Add integration test `tests/integration/test_ask_macro_comparison.py` for YoY and QoQ mock asks

### Implementation for User Story 2

- [x] T020 [US2] **Wire** planner/validator to set `quarterly_metric_cue` on `MacroBindingProposal` from `detect_quarterly_metric_cue()` (T006a); do not duplicate detection logic in `validator.py`
- [x] T021 [US2] Extend `MacroPlan.temporal_scope` / `MacroBindingRecord` with `comparison_mode` in `src/models/query.py` and wire through `macro_router.py`
- [x] T022 [US2] Filter `evidence_chunks` to bound accessions only in `src/retrieval/orchestration/nodes/micro_extractor.py` when multi-filing (verify existing `allowed_document_ids`)

**Checkpoint**: US2 integration tests pass; trajectory lists two accessions for comparison queries

---

## Phase 6: User Story 3 - Misalignment Detection and Fail-Closed (Priority: P2)

**Goal**: Incompatible periods or missing comparison partners fail closed with explicit scope message; narrow only when single anchor remains

**Independent Test**: Injected sparse corpus + comparison query returns scope error, no SUCCESS with fabricated figures (FR-010)

### Tests for User Story 3

- [x] T023 [P] [US3] Add integration test `tests/integration/test_ask_macro_fail_closed.py` (≥10 scenarios per SC-004)
- [x] T024 [P] [US3] Add unit tests for ambiguous QoQ+YoY and missing prior-year quarter in `tests/unit/test_macro_validator_misalignment.py`

### Implementation for User Story 3

- [x] T025 [US3] **Verify** fail-closed and narrow-path behavior via integration tests only (no new validator logic; extend `test_macro_validator.py` if gaps found during T023)
- [x] T026 [US3] Return scope-error `AnswerPackage` and `QueryStatus` without meso evidence in `src/retrieval/service.py` when `validation_status=failed`
- [x] T027 [US3] Surface user-visible failure message with failure codes and corpus guidance in `src/cli/commands/ask.py` stdout path

**Checkpoint**: SC-004 scenarios pass; no SUCCESS on failed macro binding

---

## Phase 7: User Story 5 - Benchmark Filing-Set Accuracy (Priority: P2)

**Goal**: FinAgentBench macro slice (≥50 items, ≥80% multi-filing) with ≥70% accession set match vs `expected_bindings`

**Independent Test**: `uv run pytest tests/integration/test_macro_binding_benchmark.py -q` meets SC-002 threshold on fixture or pilot corpus

### Tests for User Story 5

- [x] T035 [P] [US5] Add integration test `tests/integration/test_macro_binding_benchmark.py` computing `macro_binding_accuracy` per `contracts/macro-eval-harness.md`

### Implementation for User Story 5

- [x] T036 [P] [US5] Author `data/benchmarks/finagentbench/macro_binding.jsonl` (≥50 rows, ≥80% `multi_filing_required=true`) per `contracts/macro-eval-harness.md`
- [x] T037 [P] [US5] Implement `macro_binding_accuracy()` in `src/evaluation/metrics/macro_binding.py`
- [x] T038 [US5] Extend `FinAgentBenchDataset` in `src/evaluation/datasets/finagentbench.py` with `load_macro_binding_slice()`
- [x] T039 [US5] Register macro-binding eval runner in `src/evaluation/registry.py` or extend `agent-query test` in `src/cli/commands/`
- [x] T040 [US5] Add `multi_filing_required` optional field to `BenchmarkItem` in `src/models/evaluation.py` if not JSONL-only

**Checkpoint**: Benchmark gate documented; SC-001/SC-002 measurable in CI or documented offline job

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs, README, layer boundaries, quickstart validation, SC-005 usability gate

- [x] T041 [P] Add README section for autonomous macro routing and eval commands in `README.md`
- [x] T042 [P] Add contract test `tests/contract/test_macro_layer_boundaries.py` ensuring `evaluation/` does not import `retrieval/macro/planner.py`
- [x] T043 Run `specs/008-autonomous-macro-routing/quickstart.md` scenarios and fix gaps; **complete T045 SC-005 usability checklist** before marking feature done
- [x] T044 [P] Mark completed tasks in `specs/008-autonomous-macro-routing/tasks.md` after `/speckit-implement`
- [x] T045 [P] Add `docs/macro-trace-usability-checklist.md` (procedure + pass criteria); record timed results in `specs/008-autonomous-macro-routing/checklists/usability-sc005.md` (SC-005, 5 queries, ≤30s each)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP**
- **US4 (Phase 4)**: Depends on US1 (`macro_router` emits `MacroBindingRecord`) — **MVP auditability** (T028–T031 minimum before STOP)
- **US2 (Phase 5)**: Depends on Foundational + US1 router; benefits from US4 trajectory for comparison debugging
- **US3 (Phase 6)**: Depends on validator (T008+); integrates with US1/US4 service path
- **US5 (Phase 7)**: Depends on US1 autonomous path (+ US2 for multi-filing benchmark items); can run in parallel with US3 polish
- **Polish (Phase 8)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Independent test |
|-------|------------|-------------------|
| US1 | Phase 2 | NL single-filing ask |
| US4 | US1 | MLflow + stderr trace |
| US2 | Phase 2, US1 router | YoY/QoQ two accessions |
| US3 | Phase 2, US1 service | Fail-closed asks |
| US5 | US1 (+ US2 for multi-filing items) | Benchmark JSONL gate |

### Parallel Opportunities

- T002, T003, T004 in Setup
- T006a after T002; T006 after T006a; T008 after T006
- T005–T010 in Foundational (validator T008 after pairing T006)
- T013–T014 US1 tests + planner in parallel
- T028–T029, T029a US4 tests in parallel after US1
- T018–T019 US2 tests in parallel
- T036–T037 US5 dataset + metric in parallel

---

## Parallel Example: Foundational

```bash
# After T002 macro_phrases.yaml:
# T006a quarterly_metric_cue, then T006 pairing.py
uv run pytest tests/unit/test_macro_pairing.py -q   # T007
# In parallel:
# Implement validator T008 then:
uv run pytest tests/unit/test_macro_validator.py -q  # T009, T010
```

---

## Parallel Example: User Story 4

```bash
# After US1 macro_router lands:
# T028 contract schema + T030 MLflow log_macro_binding in parallel
# Then T031 trace_payloads + T032 console registry
# T029a batch audit can run once T030 lands
```

---

## Implementation Strategy

### MVP First (User Story 1 + trajectory)

1. Complete Phase 1–2 (Setup + Foundational)
2. Complete Phase 3 (US1): NL autonomous binding works end-to-end
3. Complete Phase 4 minimal (US4): T028–T031 trajectory logging
4. **STOP and VALIDATE** with quickstart §1–§3

### Incremental Delivery

1. Foundational → US1 (MVP) → **US4 (T028–T031)** → STOP per quickstart §1–§3
2. US2 multi-filing comparisons
3. US3 fail-closed hardening (tests/surfacing only if validator done in Phase 2)
4. US4 remainder (T032–T034, T029a) + US5 benchmark gate

### Suggested MVP Scope

**Phases 1–4 + T028–T031 only** — single-filing NL binding with trajectory artifact; defer T029a full batch, T045 (SC-005), and US5 until post-MVP.

---

## Notes

- Validator tests MUST NOT call live LLM (`USE_MOCK_LLM=1` or stub proposals only)
- Do not change meso/micro ranking logic except accession filtering verification (T022)
- Commit after each phase checkpoint
- Total tasks: **47** (T001–T045 plus T006a and T029a)
