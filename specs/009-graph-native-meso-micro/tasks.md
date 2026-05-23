---
description: "Task list for graph-native meso and micro navigation (009)"
---

# Tasks: Graph-Native Meso and Micro Agentic Navigation

**Input**: Design documents from `specs/009-graph-native-meso-micro/`

**Prerequisites**: `004-docling-graph-materialization`, `008-autonomous-macro-routing`, `007-ask-console-trace` on branch; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit, contract, and integration tests per plan and spec independent-test criteria (validator determinism, trajectory schema, gold-path benchmark gates SC-003–SC-005).

**Organization**: Foundational navigation package blocks all stories; **US1 meso is MVP**; **US3 trajectory immediately after US1+US2**; US4 gold-path is P2 eval slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/retrieval/navigation/`, `configs/graph_navigation.yaml`, `src/evaluation/metrics/gold_path.py`, `tests/fixtures/gold_path/`
- Extend: `src/graph/edge_catalog.py`, `src/graph/query_api.py`, `src/retrieval/orchestration/nodes/meso_router.py`, `src/retrieval/orchestration/nodes/micro_extractor.py`, `src/tracing/mlflow_langgraph.py`, `src/retrieval/orchestration/trace_payloads.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Navigation package scaffold, budget config, planner and gold-path fixture stubs

- [ ] T001 Create `src/retrieval/navigation/__init__.py` and package exports per `plan.md`
- [ ] T002 [P] Add `configs/graph_navigation.yaml` with defaults from `research.md` R6 (`meso.max_hops_per_filing`, `micro.max_hops_per_section`, `query.max_total_visits`, etc.)
- [ ] T003 [P] Add `tests/fixtures/navigation_planner/` directory with meso/micro `USE_MOCK_LLM` JSON stubs per `contracts/hop-proposal-validator.md`
- [ ] T004 [P] Add `tests/fixtures/gold_path/gold_path.jsonl` skeleton (≥5 placeholder rows) and `tests/fixtures/gold_path/manifest.json` referencing `aapl_macro_snapshot`

**Checkpoint**: `uv run python -c "from retrieval.navigation import models"` succeeds after T001

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Structural-only agent policy, graph API extensions, typed models, deterministic validator, walker loops — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T005 [P] Implement `HopProposal`, `HopCandidate`, `HopValidationResult`, `NavigationVisit`, `NavigationPath`, `MesoRankRecord`, `NavigationTraceRecord` in `src/retrieval/navigation/models.py` per `data-model.md`
- [ ] T005a [P] Extend `SectionCandidate` and `EvidenceChunk` in `src/models/query.py` with `edge_types`, `accession`, and `navigation_path_id` per `data-model.md`
- [ ] T006 [P] Implement `NavigationBudgetState` and YAML loader in `src/retrieval/navigation/budget.py` reading `configs/graph_navigation.yaml`
- [ ] T007 Narrow `AGENT_TRAVERSAL_POLICY` to `STRUCTURAL_EDGE_TYPES` only in `src/graph/edge_catalog.py` per `contracts/graph-navigation-policy.md`
- [ ] T008 [P] Extend `GraphQueryAPI` / `LocalGraphQueryAPI` in `src/graph/query_api.py` with `document_roots_for_filings()`, `outgoing_edges()`, and `navigable_node_count()` per `research.md` R7
- [ ] T009 Implement `validate_hop_proposal()` in `src/retrieval/navigation/validator.py` per `contracts/hop-proposal-validator.md` (structural edges, scope, budgets, rejection codes)
- [ ] T010 Implement `propose_next_hop()` in `src/retrieval/navigation/planner.py` with `USE_MOCK_LLM` fixture loading from `tests/fixtures/navigation_planner/` (**before** walker; FR-002/002a)
- [ ] T011 [P] Add `tests/unit/test_navigation_validator.py` covering all rejection codes in `contracts/hop-proposal-validator.md`
- [ ] T012 [P] Add `tests/unit/test_navigation_validator_scope.py` for cross-accession and disallowed `TEMPORAL_TRANSITION` / `SEMANTIC_SIMILARITY` rejects
- [ ] T014 [P] Add `tests/contract/test_navigation_layer_boundaries.py` asserting `evaluation/` does not import `retrieval.navigation.planner`
- [ ] T015 Implement `walk_meso()` and `walk_micro()` in `src/retrieval/navigation/walker.py` using validator + planner + budget state; enforce top-3 section handoff helper (depends on T010)
- [ ] T013 [P] Add `tests/unit/test_navigation_walker_budget.py` for hop/visit cap exhaustion and `stop_reason=budget` (depends on T015)

**Checkpoint**: `uv run pytest tests/unit/test_navigation_validator.py tests/unit/test_navigation_walker_budget.py -q` passes (run walker tests after T015)

---

## Phase 3: User Story 1 - Section Discovery via Disclosure Graph (Priority: P1) 🎯 MVP

**Goal**: Meso ranks sections by structural graph walks from each macro-bound document root; visit trace records node ids and edge types; top 3 per filing identified for micro

**Independent Test**: `USE_MOCK_LLM=1` ask (or direct `meso_router` on fixture state) shows meso `graph_traversal` / partial `navigation_trace` visits with structural `edge_type` values (`CONTAINS`, `NEXT`, etc.) within macro-bound accessions. **Do not** require `navigation_trace.json` or `navigation_mode` until US3 (T029–T032).

### Tests for User Story 1

- [ ] T016 [P] [US1] Add `tests/integration/test_meso_graph_navigation.py` asserting meso ranks stay within macro-bound accessions, ≤3 `micro_eligible` sections per filing, and each meso visit record includes `edge_type` + `stage=meso` on `AgentState` (not MLflow artifact)

### Implementation for User Story 1

- [ ] T017 [US1] Refactor `meso_router()` in `src/retrieval/orchestration/nodes/meso_router.py` to call `walk_meso()` per filing document root via `graph_api` (remove flat `sections_for_filings` + `score_section` as default path)
- [ ] T018 [US1] Populate `section_candidates` and `meso_section_trace` from `MesoRankRecord` paths (include `edge_types`, `accession`) in `src/retrieval/orchestration/nodes/meso_router.py`
- [ ] T019 [US1] Update `graph_traversal` state entries to include `edge_type` and `stage=meso` per visit in `src/retrieval/orchestration/nodes/meso_router.py`
- [ ] T020 [US1] Store partial `navigation_trace` meso fields on `AgentState` in `src/retrieval/orchestration/state.py` for downstream micro and trajectory

**Checkpoint**: US1 integration test passes; meso no longer uses heuristic-only default

---

## Phase 4: User Story 2 - Multi-Hop Evidence Extraction (Priority: P1)

**Goal**: Micro traverses structural paths from top-3 sections per filing; collects table/footnote/paragraph/XBRL chunk evidence with multi-hop path records

**Independent Test**: Gold-path stub or `USE_MOCK_LLM=1` ask on footnote/table query retrieves chunks linked via `FOOTNOTE_OF` or `REFERENCES` visible in `micro_paths`

### Tests for User Story 2

- [ ] T021 [P] [US2] Add `tests/integration/test_micro_multihop_paths.py` for section → table → footnote path per spec US2 acceptance scenario 2
- [ ] T022 [P] [US2] Add `tests/unit/test_micro_chunk_from_path.py` verifying evidence chunks map to terminal navigable nodes only
- [ ] T022a [P] [US2] Add `tests/integration/test_synthesis_navigation_grounding.py` asserting synthesis input evidence is a subset of graph-walked micro chunks only (FR-010 / SC-005 smoke)

### Implementation for User Story 2

- [ ] T023 [US2] Refactor `micro_extractor()` in `src/retrieval/orchestration/nodes/micro_extractor.py` to call `walk_micro()` from each micro-eligible section (top 3 per filing); remove global snapshot node scan as default
- [ ] T024 [US2] Build `EvidenceChunk` list from micro terminal nodes; attach `navigation_path_id` and `edge_types` on chunks in `src/retrieval/orchestration/nodes/micro_extractor.py`
- [ ] T025 [US2] Merge `micro_paths` and visit counts into `navigation_trace` on `AgentState` in `src/retrieval/orchestration/nodes/micro_extractor.py`
- [ ] T026 [US2] Ensure `src/retrieval/service.py` returns `INSUFFICIENT_EVIDENCE` with persisted partial trace when micro yields zero chunks (FR-013a; no heuristic fallback)

**Checkpoint**: US2 tests pass; synthesis receives only graph-walked chunks

---

## Phase 5: User Story 3 - Auditable Navigation Trace (Priority: P1)

**Goal**: Every ask persists `navigation_trace.json` and console meso/micro panels expose edge types, paths, rejections, and scan_ratio (SC-001, SC-002)

**Independent Test**: `tests/integration/test_ask_navigation_trajectory.py` asserts MLflow artifact keys; manual five-query SC-002 checklist optional in polish

### Tests for User Story 3

- [ ] T027 [P] [US3] Add contract test `tests/contract/test_navigation_trajectory_schema.py` per `contracts/navigation-trajectory.md`
- [ ] T028 [P] [US3] Add integration test `tests/integration/test_ask_navigation_trajectory.py` for `navigation_trace.json` on mock ask (SC-001 smoke)

### Implementation for User Story 3

- [ ] T029 [US3] Implement `log_navigation_trace()` in `src/tracing/mlflow_langgraph.py` and invoke from `src/retrieval/service.py` after meso/micro complete
- [ ] T030 [US3] Extend `build_meso_router_trace_payload()` and `build_micro_extractor_trace_payload()` in `src/retrieval/orchestration/trace_payloads.py` with `navigation_mode`, `edge_types_used`, `sample_path`, `rejected_count`, `visit_count`
- [ ] T031 [US3] Update meso/micro renderers in `src/tracing/console_trace/registry.py` for graph-native fields at normal and verbose depth
- [ ] T032 [US3] Add `navigation_trace` to `TrajectoryRecord` / `build_trajectory_from_state()` in `src/tracing/mlflow_langgraph.py`
- [ ] T033 [US3] Compute `scan_ratio` in walker or service using `navigable_node_count()` for trajectory and eval harness consumption

**Checkpoint**: Contract + integration trajectory tests pass; console trace shows edge types on representative ask

---

## Phase 6: User Story 4 - Gold-Path Reachability (Priority: P2)

**Goal**: ≥40-item gold-path fixture; CI gate ≥75% chunk reach without full-graph scan (SC-003); ≥90% path pattern match on reached items (SC-004)

**Independent Test**: `USE_MOCK_LLM=1 uv run agent-query test --gold-path --ticker AAPL` exits 0 with `chunk_reach_rate >= 0.75`

### Tests for User Story 4

- [ ] T034 [P] [US4] Add `tests/integration/test_gold_path_benchmark.py` asserting SC-003 and SC-004 thresholds against `tests/fixtures/gold_path/gold_path.jsonl`

### Implementation for User Story 4

- [ ] T035 [US4] Expand `tests/fixtures/gold_path/gold_path.jsonl` to ≥40 labeled items (single- and multi-filing) with `required_chunk_node_ids` and `acceptable_edge_sequences` per `contracts/gold-path-eval-harness.md`
- [ ] T036 [P] [US4] Implement `chunk_reach_rate`, `path_match_rate`, and `scan_ratio` in `src/evaluation/metrics/gold_path.py`
- [ ] T037 [US4] Add `load_gold_path_slice()` to `src/evaluation/datasets/finagentbench.py`
- [ ] T038 [US4] Add `--gold-path` flag to `src/cli/commands/test.py` wiring gold-path benchmark runner
- [ ] T039 [P] [US4] Optional: add `src/cli/gold_path_labeler.py` offline helper to draft labels from mock walks (document in quickstart only)

**Checkpoint**: Gold-path integration test passes in CI with `USE_MOCK_LLM=1`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, grounding checks, full regression, usability sign-off

- [ ] T040 [P] Update `README.md` with graph-native meso/micro navigation and `--gold-path` eval instructions
- [ ] T041 Run `quickstart.md` commands and fix any drift in docs or CLI flags
- [ ] T042 [P] Add `docs/navigation-trace-usability-checklist.md` for SC-002 five-query manual review template
- [ ] T043 [P] Add grounding assertion helper for gold-path subset (SC-005) in `tests/integration/test_gold_path_grounding.py` or extend `test_gold_path_benchmark.py`
- [ ] T044 Run full 009 test slice: `USE_MOCK_LLM=1 uv run pytest tests/unit/test_navigation*.py tests/contract/test_navigation*.py tests/integration/test_*navigation*.py tests/integration/test_gold_path*.py -q`
- [ ] T045 Verify `rank_sections_heuristic` / legacy aliases either removed or raise explicit error when called in production path per FR-013

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP**
- **US2 (Phase 4)**: Depends on US1 meso ranks / top-3 handoff
- **US3 (Phase 5)**: Depends on US1 + US2 for complete `navigation_trace` (meso-only artifact acceptable mid-phase for smoke)
- **US4 (Phase 6)**: Depends on US1–US3 (needs walk + trace + `scan_ratio`)
- **Polish (Phase 7)**: Depends on desired story completion

### User Story Dependencies

| Story | Depends on | Independent test |
|-------|------------|------------------|
| US1 | Foundational | Meso graph navigation integration test |
| US2 | US1 | Multi-hop micro path integration test |
| US3 | US1, US2 | Trajectory schema + MLflow smoke |
| US4 | US1–US3 | `--gold-path` benchmark gate |

### Parallel Opportunities

- Phase 1: T002–T004 in parallel
- Phase 2: T005–T008, T005a, T011–T012, T014 in parallel after T001; then T010 → T015 → T013 sequentially
- US1: T016 parallel with T017 prep; US2: T021–T022 parallel
- US3: T027–T028 parallel; US4: T034–T036 parallel after fixture T035 started

---

## Parallel Example: Foundational Phase

```bash
# Models + graph API + tests in parallel:
# T005 src/retrieval/navigation/models.py
# T008 src/graph/query_api.py
# T011 tests/unit/test_navigation_validator.py
```

---

## Parallel Example: User Story 3

```bash
# Contract + integration tests together:
# T027 tests/contract/test_navigation_trajectory_schema.py
# T028 tests/integration/test_ask_navigation_trajectory.py
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1–2 (Setup + Foundational)
2. Complete Phase 3 (US1 meso graph navigation)
3. **STOP and VALIDATE**: `test_meso_graph_navigation.py` + ask smoke with trace
4. Add US2 → US3 → US4 incrementally

### Suggested commit order

1. Foundational package + graph API (T001–T015)
2. US1 meso (T016–T020)
3. US2 micro (T021–T026)
4. US3 trajectory (T027–T033)
5. US4 gold-path (T034–T039)
6. Polish (T040–T045)

---

## Notes

- Total tasks: **47** (T001–T045, T005a, T022a)
- Per story: Setup 4, Foundational 12, US1 5, US2 7, US3 7, US4 6, Polish 6
- **Analyze remediation (2026-05-23)**: T010/T015 planner-before-walker; US1 test scoped to AgentState; T005a query models; T022a synthesis grounding
- All tasks use checklist format with file paths
- Do not count full-graph diagnostic enumeration toward SC-003 (see spec assumptions)
- `CHUNK_XBRL_FACT` nodes are valid micro targets via structural `CONTAINS` only (`research.md` R10)
