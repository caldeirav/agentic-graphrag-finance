---
description: "Task list for Agentic SEC Disclosure Reasoning & Benchmarking"
---

# Tasks: Agentic SEC Disclosure Reasoning & Benchmarking

**Input**: Design documents from `specs/001-sec-disclosure-rag/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Contract and integration tests included per constitution quality gates (not full TDD). Use `USE_MOCK_LLM=1` in CI for retrieval/eval integration tests.

**Organization**: Tasks grouped by user story (P1 → P2 → P3) per spec.md priorities.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[USn]**: User story label (US1 = ingestion/graph, US2 = agentic retrieval, US3 = benchmarks)

## Path Conventions

- Single Python monorepo: `src/`, `tests/`, `configs/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Segment S0 — reproducible workspace and project skeleton

- [ ] T001 Initialize `pyproject.toml` with `uv init`, `requires-python >= 3.12`, and package layout in `src/`
- [ ] T002 Add locked dependencies (`langchain`, `langgraph`, `langchain-openai`, `langchain-google-genai`, `docling`, `docling-graph`, `mlflow`, `pydantic`, `networkx`, `pytest`, `ruff`, `mypy`) via `uv add` and commit `uv.lock`
- [ ] T003 Create `.env.example` with `LM_STUDIO_BASE_URL`, `LM_STUDIO_MODEL`, `GOOGLE_API_KEY`, `MLFLOW_TRACKING_URI` at repository root
- [ ] T004 [P] Scaffold layer packages with `__init__.py` in `src/parsing/`, `src/graph/`, `src/retrieval/`, `src/retrieval/orchestration/`, `src/retrieval/orchestration/nodes/`, `src/tracing/`, `src/evaluation/`, `src/evaluation/datasets/`, `src/evaluation/judges/`, `src/evaluation/metrics/`, `src/models/`, `src/contracts/`
- [ ] T005 [P] Add `configs/docling_xbrl.yaml`, `configs/lm_studio.yaml`, `configs/mlflow.yaml`, `configs/judges/gemini_2_5_pro.yaml`
- [ ] T006 [P] Configure `ruff`, `mypy` (strict on `src/models` and `src/contracts`), and `pytest` in `pyproject.toml`
- [ ] T007 Update `.gitignore` for `data/`, `mlruns/`, `.env`, `__pycache__/`, `.venv/`
- [ ] T008 Add CI workflow (e.g. `.github/workflows/ci.yml`) running `uv sync --locked`, `ruff check`, `mypy`, and `pytest tests/unit tests/contract`

**Checkpoint**: `uv sync --locked` succeeds; empty packages importable

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, contracts, and test harness — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T009 Implement core Pydantic models (`FilingRef`, `ParsedDocument`, `GraphNode`, `GraphEdge`, `GraphSnapshot`, `EvidenceChunk`, `AnswerPackage`, `TrajectoryRecord`, `BenchmarkItem`, `EvaluationRun`) in `src/models/`
- [ ] T010 Implement cross-layer DTOs `QueryRequest` and `QueryResponse` in `src/contracts/query.py` per `contracts/layer-boundaries.md`
- [ ] T011 [P] Add `GraphQueryAPI` Protocol and stub implementation in `src/graph/query_api.py`
- [ ] T012 [P] Add import-boundary contract tests in `tests/contract/test_layer_imports.py` (parsing ↛ graph retrieval; evaluation ↛ retrieval.orchestration)
- [ ] T013 [P] Create `tests/conftest.py` with `USE_MOCK_LLM` fixture and sample `GraphSnapshot` factory in `tests/fixtures/graph_snapshot.json`
- [ ] T014 [P] Add unit tests for Pydantic model validation edge cases in `tests/unit/test_models.py`
- [ ] T015 Create `data/` directory layout placeholders (`data/raw/edgar/`, `data/parsed/`, `data/graphs/`, `data/benchmarks/`) documented in `README.md`

**Checkpoint**: Models importable; contract tests pass (may skip graph-dependent assertions until US1)

---

## Phase 3: User Story 1 - Structured Filing Ingestion & Knowledge Graph (Priority: P1) 🎯 MVP

**Goal**: Ingest SEC 10-K/10-Q with layout preservation; build hierarchical knowledge graph (document → section → chunk) with temporal edges

**Independent Test**: Ingest one issuer 10-K + 10-Q; verify graph hierarchy, preserved financial table headers, and footnote linkage traceable to parent chunk

### Implementation for User Story 1

- [ ] T016 [P] [US1] Implement EDGAR fetch helper in `src/parsing/edgar_fetch.py` (CIK, accession, form type 10-K/10-Q)
- [ ] T017 [P] [US1] Implement Docling XBRL pipeline wrapper loading `configs/docling_xbrl.yaml` in `src/parsing/docling_pipeline.py`
- [ ] T018 [US1] Map Docling output to `ParsedDocument` (sections, tables, footnotes, `content_hash`) in `src/parsing/docling_pipeline.py`
- [ ] T019 [US1] Implement fail-closed parse validators (`parse_confidence` threshold) in `src/parsing/validators.py`
- [ ] T020 [US1] Implement docling-graph → `GraphSnapshot` mapper with node types (`DOCUMENT`, `SECTION`, `CHUNK_*`) in `src/graph/builder.py`
- [ ] T021 [US1] Emit typed edges (`CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`, `TEMPORAL_TRANSITION`) in `src/graph/builder.py`
- [ ] T022 [US1] Implement GraphML + `manifest.json` persistence in `src/graph/store.py`
- [ ] T023 [US1] Implement read-only `GraphQueryAPI` (get_snapshot, get_node, neighbors, sections_for_filings) in `src/graph/query_api.py`
- [ ] T024 [US1] Add `src/parsing/cli.py` ingest command writing to `data/raw/` and `data/parsed/`
- [ ] T025 [US1] Add `src/graph/cli.py` build command writing to `data/graphs/{issuer_id}/`
- [ ] T026 [P] [US1] Add contract test parsing→graph boundary in `tests/contract/test_parsing_graph.py`
- [ ] T027 [P] [US1] Add integration test with golden SEC excerpt fixture in `tests/integration/test_ingest_graph.py`
- [ ] T028 [US1] Add structure regression test asserting table headers survive parse in `tests/unit/test_parsing_structure.py`

**Checkpoint**: `uv run python -m graph.cli build` produces queryable snapshot; US1 independent test passes

---

## Phase 4: User Story 2 - Multi-Stage Agentic Query Resolution (Priority: P2)

**Goal**: LangGraph macro → meso → micro routing with local Qwen (LM Studio); grounded answers with citations; MLflow trajectories

**Independent Test**: Run 50-question pilot (or subset) against US1 corpus; ≥80% answers cite supporting chunks; 100% fail-closed when evidence missing

**Depends on**: Phase 3 complete (graph snapshot available)

### Implementation for User Story 2

- [ ] T029 [US2] Define typed `AgentState` and routing DTOs (`MacroPlan`, `SectionCandidate`, `QueryStatus`) in `src/retrieval/orchestration/state.py`
- [ ] T030 [US2] Implement LM Studio `ChatOpenAI` factory from `configs/lm_studio.yaml` in `src/retrieval/orchestration/llm.py`
- [ ] T031 [US2] Implement `macro_router` node (temporal scope + `filing_set`) in `src/retrieval/orchestration/nodes/macro_router.py`
- [ ] T032 [US2] Implement `meso_router` node (section ranking via `GraphQueryAPI`) in `src/retrieval/orchestration/nodes/meso_router.py`
- [ ] T033 [US2] Implement `micro_extractor` node (chunk/cell selection) in `src/retrieval/orchestration/nodes/micro_extractor.py`
- [ ] T034 [US2] Implement grounded `synthesize` node with `InsufficientEvidence` fail-closed path in `src/retrieval/synthesis.py`
- [ ] T035 [US2] Compile LangGraph `StateGraph` (macro → meso → micro → synthesize) in `src/retrieval/orchestration/graph.py` per `contracts/langgraph-state.md`
- [ ] T036 [US2] Implement `QueryService.answer()` façade returning `QueryResponse` in `src/retrieval/service.py`
- [ ] T037 [US2] Implement MLflow setup and LangGraph autolog wrapper in `src/tracing/mlflow_langgraph.py`
- [ ] T038 [US2] Log `TrajectoryRecord` JSON artifact (plan, document route, graph traversal, evidence) per query in `src/tracing/mlflow_langgraph.py`
- [ ] T039 [US2] Integrate tracing wrapper into `QueryService` (parent run, params, per-node metrics) in `src/retrieval/service.py`
- [ ] T040 [US2] Add `src/retrieval/cli.py` query command accepting `--snapshot-id` and `--question`
- [ ] T041 [P] [US2] Add contract test `QueryService` public API in `tests/contract/test_retrieval_contract.py`
- [ ] T042 [P] [US2] Add integration test with `USE_MOCK_LLM=1` for full graph invoke in `tests/integration/test_query_flow.py`
- [ ] T043 [US2] Add trace contract test asserting mandatory `TrajectoryRecord` fields in `tests/contract/test_trajectory_artifact.py`

**Checkpoint**: `uv run python -m retrieval.cli query` returns cited answer; MLflow run shows LangGraph spans + `trajectory.json`

---

## Phase 5: User Story 3 - Industry Benchmark Evaluation (Priority: P3)

**Goal**: Modular FinDER / FinAgentBench / FinanceBench runners; Gemini 2.5 Pro judge; MRR/MAP/nDCG + trajectory fidelity reports

**Independent Test**: Run pilot suite (≤100 items/dataset); produce per-dataset and per-operation-class reports with MLflow run IDs; add/remove dataset plugin without retrieval code changes

**Depends on**: Phase 4 complete (`QueryService` + trajectories)

### Implementation for User Story 3

- [ ] T044 [US3] Implement `BenchmarkDataset` protocol and registry in `src/evaluation/registry.py` per `contracts/benchmark-registry.md`
- [ ] T045 [P] [US3] Implement FinDER adapter in `src/evaluation/datasets/finder.py`
- [ ] T046 [P] [US3] Implement FinAgentBench adapter in `src/evaluation/datasets/finagentbench.py`
- [ ] T047 [P] [US3] Implement FinanceBench adapter in `src/evaluation/datasets/financebench.py`
- [ ] T048 [US3] Implement Gemini 2.5 Pro judge with rubrics from `configs/judges/gemini_2_5_pro.yaml` in `src/evaluation/judges/gemini_panel.py`
- [ ] T049 [P] [US3] Implement MRR, MAP, nDCG@k in `src/evaluation/metrics/ranking.py`
- [ ] T050 [P] [US3] Implement trajectory fidelity aggregation in `src/evaluation/metrics/trajectory.py`
- [ ] T051 [US3] Implement `EvaluationRunner` invoking `QueryService` per item in `src/evaluation/runner.py`
- [ ] T052 [US3] Generate stratified reports (`by_dataset`, `by_operation_class`) and log to MLflow parent run in `src/evaluation/runner.py`
- [ ] T053 [US3] Add `src/evaluation/cli.py` benchmark command (`--suite`, `--snapshot-id`, `--datasets`, `--max-items`)
- [ ] T054 [P] [US3] Add contract test evaluation layer does not import `retrieval.orchestration` in `tests/contract/test_evaluation_imports.py`
- [ ] T055 [US3] Add integration test for registry plug-in swap (mock dataset) in `tests/integration/test_benchmark_registry.py`
- [ ] T056 [US3] Add evaluation smoke test (1 item, mock LLM + mock judge) in `tests/integration/test_benchmark_smoke.py`

**Checkpoint**: `uv run python -m evaluation.cli benchmark --suite pilot` produces `summary.json` and MLflow parent run

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, reproducibility, and constitution compliance hardening

- [ ] T057 [P] Add root `README.md` with architecture overview, layer diagram, and links to `specs/001-sec-disclosure-rag/quickstart.md`
- [ ] T058 Validate `quickstart.md` commands against implemented CLIs; update quickstart if flags differ
- [ ] T059 [P] Add `tests/unit/test_fail_closed.py` covering missing filing period and empty evidence paths
- [ ] T060 [P] Add golden-fixture numeric spot-check test for graph navigation in `tests/integration/test_graph_numeric_trace.py`
- [ ] T061 Configure optional `import-linter` or ruff banned-import rules enforcing layer boundaries in `pyproject.toml`
- [ ] T062 Document benchmark reproduction steps (frozen snapshot, judge config hash, MLflow run ID) in `docs/benchmark-reproduction.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **blocks US2 and US3**
- **US2 (Phase 4)**: Depends on US1 (requires graph snapshots)
- **US3 (Phase 5)**: Depends on US2 (requires `QueryService` + trajectories)
- **Polish (Phase 6)**: Depends on desired user stories being complete

### User Story Dependencies

```text
US1 (P1) ──► US2 (P2) ──► US3 (P3)
```

US2 and US3 are not parallelizable until prior story checkpoints pass.

### Within Each User Story

- Models/contracts before services
- Core implementation before CLI
- Contract tests can proceed in parallel once interfaces exist ([P] tasks)
- Integration tests last within each story

### Parallel Opportunities

**Phase 1**: T004, T005, T006 in parallel  
**Phase 2**: T011, T012, T013, T014 in parallel  
**Phase 3**: T016+T017 parallel; T026+T027+T028 parallel after core ingest  
**Phase 4**: T041+T042 parallel after T036  
**Phase 5**: T045+T046+T047 parallel; T049+T050 parallel  
**Phase 6**: T057, T059, T060 parallel  

---

## Parallel Example: User Story 1

```bash
# After T015, launch in parallel:
# Task T016: src/parsing/edgar_fetch.py
# Task T017: src/parsing/docling_pipeline.py (config loader)

# After T022, launch in parallel:
# Task T026: tests/contract/test_parsing_graph.py
# Task T027: tests/integration/test_ingest_graph.py
# Task T028: tests/unit/test_parsing_structure.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational  
3. Complete Phase 3: User Story 1  
4. **STOP and VALIDATE**: Run US1 independent test (ingest + graph trace)  
5. Demo browsable graph snapshot before building retrieval

### Incremental Delivery

1. Setup + Foundational → foundation ready  
2. Add US1 → Validate independently → **MVP** (structured disclosure graph)  
3. Add US2 → Validate Q&A + MLflow traces  
4. Add US3 → Validate benchmark pilot + judge reports  
5. Polish → CI hardening + reproduction docs  

### Suggested MVP Scope

**User Story 1 only** (T001–T028): Delivers constitution-aligned parsing and graph layers without LLM or benchmark dependencies.

---

## Task Summary

| Phase | Task IDs | Count |
|-------|----------|-------|
| Setup | T001–T008 | 8 |
| Foundational | T009–T015 | 7 |
| US1 (P1) | T016–T028 | 13 |
| US2 (P2) | T029–T043 | 15 |
| US3 (P3) | T044–T056 | 13 |
| Polish | T057–T062 | 6 |
| **Total** | **T001–T062** | **62** |

**Parallel opportunities**: 18 tasks marked `[P]`  
**Independent test criteria**: Documented per user story phase header
