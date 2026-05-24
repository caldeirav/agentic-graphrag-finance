---
description: "Task list for auditable MLflow trajectories and LLM-as-judge evaluation (010)"
---

# Tasks: Auditable MLflow Trajectories & LLM-as-Judge Evaluation

**Input**: Design documents from `specs/010-mlflow-trajectory-judge-eval/`

**Prerequisites**: `007-ask-console-trace`, `008-autonomous-macro-routing`, `009-graph-native-meso-micro` on branch `010-mlflow-trajectory-judge-eval`; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Contract, unit, and integration tests per plan gap analysis, spec independent-test criteria, and constitution trace/eval gates (SC-001–SC-007).

**Organization**: Foundational typed models block all stories; **US1 trajectory export is MVP**; **US2 validator before US3 judge**; US4 integrates ask pipeline + console + benchmark gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/models/trajectory.py`, `src/tracing/trajectory_export.py`, `src/evaluation/validator/`, `src/evaluation/ask_judge.py`, `configs/trajectory_judge.yaml`, `tests/fixtures/trajectory_validation/`
- Extend: `src/tracing/mlflow_langgraph.py`, `src/retrieval/service.py`, `src/evaluation/judges/gemini_panel.py`, `src/evaluation/runner.py`, `src/tracing/console_trace/`, `configs/judges/gemini_2_5_pro.yaml`, `contracts/query.py` (QueryResponse fields)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config stubs, validator package scaffold, trajectory-validation fixtures

- [ ] T001 Add `configs/trajectory_judge.yaml` with `min_score: 0.6`, `max_retries: 3`, `backoff_seconds: [1, 2, 4]`, and criterion ids per `contracts/gemini-judge-config.md`
- [ ] T002 [P] Create `src/evaluation/validator/__init__.py` exporting `validate_trajectory` stub
- [ ] T003 [P] Create `tests/fixtures/trajectory_validation/` with `valid_complete.json`, `missing_hashes.json`, `orphan_hop.json`, `macro_failed_with_reason.json` per `contracts/trajectory-validator.md`
- [ ] T004 [P] Add `tests/fixtures/trajectory_validation/manifest.json` listing fixture files and expected validation status
- [ ] T005 [P] Extend `configs/judges/gemini_2_5_pro.yaml` with four FR-012 rubric entries (`trajectory_coherence`, `routing_decisions`, `retrieval_fidelity`, `synthesis_grounding`) per `contracts/gemini-judge-config.md`

**Checkpoint**: `uv run python -c "from evaluation.validator import validate_trajectory"` succeeds (stub returns placeholder)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic types for snapshot, validation, and judge results — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T006 [P] Add `AgentTrajectorySnapshot`, `TrajectoryPlan`, `GraphHop`, `EvidenceEntry`, `FilingRouteEntry` in `src/models/trajectory.py` per `data-model.md` and `contracts/trajectory-schema.md`
- [ ] T007 [P] Add `TrajectoryValidationResult`, `ValidationReason`, `ValidationStatus` enum in `src/models/evaluation.py` per `data-model.md`
- [ ] T008 [P] Add `JudgeCriterionResult`, `JudgeRunSummary`, `JudgeStatus` enum in `src/models/evaluation.py` per `data-model.md`
- [ ] T009 [P] Extend `JudgeVerdict` in `src/models/evaluation.py` to support four criterion ids (deprecate legacy keys via property shim documented in `contracts/gemini-judge-config.md`)
- [ ] T010 [P] Export new models from `src/models/__init__.py`
- [ ] T011 Create `src/tracing/trajectory_export.py` with `build_agent_trajectory_snapshot(state, trace_id=None) -> AgentTrajectorySnapshot` stub returning minimal valid snapshot
- [ ] T012 [P] Add `log_agent_trajectory()`, `log_trajectory_validation()`, `log_judge_verdict()` stubs in `src/tracing/mlflow_langgraph.py` per `contracts/trace-export.md`
- [ ] T013 [P] Add MLflow run tag helpers (`validation_status`, `judge_status`, `trajectory_schema_version`) in `src/tracing/mlflow_langgraph.py`

**Checkpoint**: `uv run python -c "from models.trajectory import AgentTrajectorySnapshot; from tracing.trajectory_export import build_agent_trajectory_snapshot"` succeeds

---

## Phase 3: User Story 1 - Complete Trajectory on Every Query (Priority: P1) 🎯 MVP

**Goal**: Every `ask`/benchmark run logs versioned `agent_trajectory.json` with plan, document route, graph hops, evidence, synthesis path; MLflow Trace remains primary via autolog

**Independent Test**: `USE_MOCK_LLM=1` ask produces MLflow run with `agent_trajectory.json` containing `schema_version`, populated or `absent_reason` sections; macro-failure fixture shows standardized absence codes

### Tests for User Story 1

- [ ] T014 [P] [US1] Add contract test `tests/contract/test_trajectory_schema.py` validating golden `tests/fixtures/trajectory_validation/valid_complete.json` against Pydantic models
- [ ] T015 [P] [US1] Extend `tests/contract/test_trajectory_artifact.py` to assert `agent_trajectory.json` keys and `schema_version` on mock ask run
- [ ] T016 [P] [US1] Add integration test `tests/integration/test_ask_agent_trajectory.py` for successful ask + macro-failure trajectory shape (US1 acceptance scenario 3)

### Implementation for User Story 1

- [ ] T017 [US1] Implement full `build_agent_trajectory_snapshot()` in `src/tracing/trajectory_export.py` mapping LangGraph state + `macro_binding` / `navigation_trace` / `intent_router` per `contracts/trajectory-schema.md`
- [ ] T018 [US1] Populate `plan` (intent summary, steps considered, rationale) from `macro_plan`, `macro_binding_record`, and `intent_trace` in `src/tracing/trajectory_export.py`
- [ ] T019 [US1] Map `document_route` from `filing_set` with form type, period end, fiscal labels in `src/tracing/trajectory_export.py`
- [ ] T020 [US1] Map `graph_traversal` to `GraphHop` list with `node_type`, `edge_type`, `edge_id`, `stage`, `accession_prefix` from state `graph_traversal` and `navigation_trace` in `src/tracing/trajectory_export.py`
- [ ] T021 [US1] Map `evidence` with `content_hash`, `citation_label`, `source_type`, `in_prompt` from `evidence_chunks` and synthesis budget metadata in `src/tracing/trajectory_export.py`
- [ ] T022 [US1] Record `synthesis_path` (`live_llm` | `deterministic_fallback` | `template`) from synthesis node state in `src/retrieval/orchestration/nodes/` (or export helper reading state flag set by `src/retrieval/synthesis.py`)
- [ ] T023 [US1] Implement `log_agent_trajectory()` in `src/tracing/mlflow_langgraph.py`; invoke from `src/retrieval/service.py` after graph invoke (keep legacy `trajectory.json` one release)
- [ ] T024 [US1] Set `mlflow_trace_id` on snapshot when `mlflow.get_last_active_trace_id()` available in `src/tracing/trajectory_export.py`
- [ ] T025 [P] [US1] Add optional `@mlflow.trace` span wrappers or stage tags on `macro_router`, `intent_router`, `meso_router`, `micro_extractor`, `synthesize` nodes in `src/retrieval/orchestration/nodes/` where autolog gaps exist per `research.md` R2
- [ ] T026 [US1] Ensure `build_trajectory_from_state()` in `src/tracing/mlflow_langgraph.py` delegates to `build_agent_trajectory_snapshot()` for backward compatibility

**Checkpoint**: US1 contract + integration tests pass; `agent_trajectory.json` on every mock ask

---

## Phase 4: User Story 2 - Trajectory Validator & Reproducibility Gate (Priority: P1)

**Goal**: Deterministic validator assigns `complete` | `incomplete` | `non_reproducible` with reason codes; results logged to MLflow

**Independent Test**: `uv run pytest tests/contract/test_trajectory_validator.py` — table-driven fixtures pass/fail with expected codes; incomplete runs flagged for aggregate exclusion

### Tests for User Story 2

- [ ] T027 [P] [US2] Add `tests/contract/test_trajectory_validator.py` table-driven over `tests/fixtures/trajectory_validation/*.json`
- [ ] T028 [P] [US2] Add unit test `tests/unit/test_trajectory_validator_rules.py` for each reason code in `contracts/trajectory-validator.md`

### Implementation for User Story 2

- [ ] T029 [US2] Implement `validate_trajectory(snapshot: AgentTrajectorySnapshot) -> TrajectoryValidationResult` in `src/evaluation/validator/trajectory.py` per `contracts/trajectory-validator.md`
- [ ] T030 [US2] Implement rules: missing schema/plan, empty document route on success, missing node_type/edge_type, missing content_hash, orphan hop accession, evidence accession mismatch in `src/evaluation/validator/trajectory.py`
- [ ] T031 [US2] Implement macro-failure `absent_reason` acceptance (empty traversal/evidence allowed when documented) in `src/evaluation/validator/trajectory.py`
- [ ] T032 [US2] Implement `log_trajectory_validation()` in `src/tracing/mlflow_langgraph.py` writing `trajectory_validation.json`
- [ ] T033 [US2] Add `src/evaluation/validator/__init__.py` export and docstring referencing import boundary (no retrieval imports)

**Checkpoint**: Validator tests pass on all four fixtures; validation artifact shape stable

---

## Phase 5: User Story 3 - LLM-as-Judge on Trajectories (Priority: P2)

**Goal**: Gemini judge scores four criteria 0.0–1.0 with justifications; blocking on complete trajectories; retry-then-degrade; no retrieval imports in eval module

**Independent Test**: `USE_MOCK_JUDGE=1` benchmark item produces `judge_verdict.json` with four criteria; `tests/contract/test_judge_import_boundary.py` passes

### Tests for User Story 3

- [ ] T034 [P] [US3] Add `tests/contract/test_judge_import_boundary.py` forbidding `retrieval`, `ingestion`, `graph` imports under `src/evaluation/` per `contracts/judge-eval-boundary.md`
- [ ] T035 [P] [US3] Add `tests/unit/test_gemini_judge_parser.py` for JSON response parsing (no network)
- [ ] T036 [P] [US3] Add integration test `tests/integration/test_ask_judge_mlflow.py` asserting artifact order: `agent_trajectory.json` → `trajectory_validation.json` → `judge_verdict.json` with `USE_MOCK_JUDGE=1`

### Implementation for User Story 3

- [ ] T037 [US3] Refactor `GeminiJudgePanel._build_prompt()` in `src/evaluation/judges/gemini_panel.py` to include serialized snapshot + answer + four rubrics; require JSON-only response per `research.md` R5
- [ ] T038 [US3] Replace placeholder scores in `GeminiJudgePanel.judge()` with parsed `JudgeCriterionResult` list in `src/evaluation/judges/gemini_panel.py`
- [ ] T039 [US3] Implement `JudgeParseError` and mock path for `USE_MOCK_JUDGE=1` returning four heuristic scores in `src/evaluation/judges/gemini_panel.py`
- [ ] T040 [US3] Create `src/evaluation/ask_judge.py` with `judge_with_retries()` using `configs/trajectory_judge.yaml` backoff and max retries per FR-009b
- [ ] T041 [US3] Implement `run_post_query_audit(snapshot, answer, question, mlflow_run_id)` in `src/evaluation/ask_judge.py` orchestrating validate → judge (skip judge when not `complete`) per `contracts/ask-pipeline-judge.md`
- [ ] T042 [US3] Implement `log_judge_verdict()` and judge MLflow tags (`judge_weakest_criterion`, `judge_weakest_stage`, per-score tags) in `src/tracing/mlflow_langgraph.py`
- [ ] T043 [US3] Extend `src/evaluation/runner.py` to call `run_post_query_audit()` after each benchmark item (same path as production ask)
- [ ] T044 [US3] Update benchmark aggregates in `src/evaluation/runner.py` to exclude non-`complete` and `judge_status=degraded` from headline means per FR-008

**Checkpoint**: Mock judge integration test passes; import boundary test passes

---

## Phase 6: User Story 4 - Console & MLflow Operator Visibility (Priority: P2)

**Goal**: Blocking validate+judge on every `ask`; console footer ≤15 lines at `normal`; benchmark 90% gate on ≥50-item reference suite

**Independent Test**: `agent-query ask --trace normal` shows validation + judge summary; benchmark report prints exclusion counts and gate pass/fail

### Tests for User Story 4

- [ ] T045 [P] [US4] Extend `tests/integration/test_agent_query_ask.py` to assert `trajectory_audit` footer lines when `--trace normal` and `USE_MOCK_JUDGE=1`
- [ ] T046 [P] [US4] Add `tests/integration/test_benchmark_trajectory_gate.py` for 90% gate math and exclusion reporting per `contracts/benchmark-gate.md`
- [ ] T047 [P] [US4] Add contract test `tests/contract/test_judge_eval_boundary_facade.py` ensuring `retrieval/service.py` only imports `evaluation.ask_judge.run_post_query_audit`

### Implementation for User Story 4

- [ ] T048 [US4] Wire `run_post_query_audit()` into `QueryService.answer()` in `src/retrieval/service.py` after snapshot export (blocking before return) per `contracts/ask-pipeline-judge.md`
- [ ] T049 [US4] Extend `QueryResponse` in `src/contracts/query.py` with `validation_status`, `judge_status`, `judge_scores` fields
- [ ] T050 [US4] Add `build_trajectory_audit_trace_payload()` in `src/tracing/console_trace/trace_payloads.py` per FR-013 (weakest criterion/stage when score &lt; min_score)
- [ ] T051 [US4] Register `trajectory_audit` footer event in `src/tracing/console_trace/reporter.py` and emit from `QueryService` after audit
- [ ] T052 [US4] Cap audit block to ≤15 lines at `TraceLevel.NORMAL` in `src/tracing/console_trace/reporter.py` (SC-006)
- [ ] T053 [US4] Create combined reference suite config `configs/benchmarks/reference_trajectory_gate.yaml` (≥50 items: gold-path + macro-binding + trajectory-validation) per `contracts/benchmark-gate.md`
- [ ] T054 [US4] Implement gate reporter in `src/evaluation/runner.py` or `src/evaluation/gate.py` printing pass rate and `gate: PASS|FAIL`
- [ ] T055 [US4] Wire CI job step in `.github/workflows/ci.yml` running reference gate with `USE_MOCK_JUDGE=1` and `USE_FIXTURE_INGESTION=1` where applicable

**Checkpoint**: Live ask with `--trace normal` shows audit footer; CI gate fails when pass rate &lt; 90%

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, quickstart validation, legacy deprecation notes

- [ ] T056 [P] Update `README.md` with MLflow Trace + judge env vars (`GOOGLE_API_KEY`, `USE_MOCK_JUDGE`) and quickstart pointer to `specs/010-mlflow-trajectory-judge-eval/quickstart.md`
- [ ] T057 [P] Update `.env.example` if any new optional vars documented (e.g. `GEMINI_JUDGE_MODEL` only if implemented)
- [ ] T058 Run full quickstart validation from `specs/010-mlflow-trajectory-judge-eval/quickstart.md` (mock + optional live judge smoke)
- [ ] T059 [P] Add deprecation note in `specs/010-mlflow-trajectory-judge-eval/contracts/trajectory-schema.md` migration section for `trajectory.json`-only consumers
- [ ] T060 Mark all completed tasks `[x]` in this file after `/speckit-implement` verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP**
- **US2 (Phase 4)**: Depends on US1 snapshot builder (validator consumes `AgentTrajectorySnapshot`)
- **US3 (Phase 5)**: Depends on US2 (judge runs only on `complete`)
- **US4 (Phase 6)**: Depends on US3 (console + ask pipeline need judge summary)
- **Polish (Phase 7)**: Depends on US4

### User Story Dependencies

```text
Foundational → US1 → US2 → US3 → US4 → Polish
```

US2 validator can be developed in parallel with late US1 tasks only after T006–T011 models exist; full US2 tests need T017 export.

### Parallel Opportunities

- Phase 1: T002–T005 in parallel after T001
- Phase 2: T006–T010, T012–T013 in parallel
- US1 tests T014–T016 in parallel before implementation
- US2 tests T027–T028 in parallel
- US3 tests T034–T036 in parallel
- US4 tests T045–T047 in parallel
- Polish T056–T057, T059 in parallel

### Parallel Example: User Story 1

```bash
# Tests first (parallel):
tests/contract/test_trajectory_schema.py
tests/contract/test_trajectory_artifact.py
tests/integration/test_ask_agent_trajectory.py

# Then export mappers (parallel after T017):
T018 plan, T019 document_route, T020 graph_traversal, T021 evidence
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1–2
2. Complete Phase 3 (US1)
3. **STOP and VALIDATE**: `agent_trajectory.json` on mock ask; schema contract tests green
4. Demo MLflow UI Trace + artifact

### Incremental Delivery

1. US1 → auditable trajectory export (MVP)
2. US2 → validator + exclusion semantics
3. US3 → Gemini judge + benchmark parity
4. US4 → production blocking path + console + 90% CI gate
5. Polish → README and quickstart

### Suggested MVP Scope

**User Story 1** (Phases 1–3): Delivers constitution III trajectory payload without judge latency. US2–US4 add quality gates and operator visibility.

---

## Notes

- Total tasks: **60** (T001–T060)
- Per story: Setup 5 | Foundational 8 | US1 13 | US2 7 | US3 11 | US4 11 | Polish 5
- All tasks use checklist format with file paths
- Live Gemini tests optional (`@pytest.mark.live`); CI uses `USE_MOCK_JUDGE=1`
- Gap vs current code: `GeminiJudgePanel` placeholder scores, `trajectory.json`-only path, no blocking ask judge — addressed in US1/US3/US4
