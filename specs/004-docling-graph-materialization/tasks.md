---
description: "Task list for docling-graph knowledge materialization (004)"
---

# Tasks: Docling-Graph Knowledge Materialization

**Input**: Design documents from `specs/004-docling-graph-materialization/`

**Prerequisites**: `003-multi-filing-corpus` merged; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit, contract, and integration tests per plan (parity, reachability gate, layer boundaries, fail-closed materialization).

**Organization**: Tasks grouped by user story (P1 → P4) per spec.md. Extends 003 `graph/registry.py` and `agent-query materialize` — **no** ingestion or parsing contract changes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/graph/`, `src/models/`, `src/cli/`, `src/retrieval/`, `src/tracing/`
- Additive: `src/graph/docling_graph_mapper.py`, `src/graph/edge_catalog.py`, `src/graph/similarity.py`, `src/graph/reachability.py`, `src/graph/legacy_builder.py`, `src/models/graph_audit.py`, `src/cli/commands/graph_audit.py`
- Config: `configs/graph_audit.yaml`, `configs/graph_similarity.yaml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config defaults and operator docs for graph audit and similarity

- [x] T001 [P] Add `configs/graph_audit.yaml` with `hop_budget: 6`, `sample_size: 100`, `pass_threshold: 0.95`, `random_seed`, and structural edge whitelist per `contracts/reachability-audit.md`
- [x] T002 [P] Add `configs/graph_similarity.yaml` with `thematic_enabled: false`, `thematic_threshold`, and deterministic link toggles per `research.md` R3
- [x] T003 Document `agent-query graph-audit`, reachability gate, and `data/graphs/{issuer}/*.reachability.json` in `README.md` linking `specs/004-docling-graph-materialization/quickstart.md`

**Checkpoint**: Config files loadable from tests; README describes audit workflow

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Edge catalog, audit models, legacy snapshot for parity — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T004 Add `GraphNodeType.CHUNK_XBRL_FACT` and `GraphEdgeType.SEMANTIC_SIMILARITY` to `src/models/enums.py` per `contracts/edge-catalog.md`
- [x] T005 Add Pydantic models `ReachabilityAuditReport`, `AuditEntry`, `FilingMaterializationResult` in `src/models/graph_audit.py` per `data-model.md`
- [x] T006 Implement `src/graph/edge_catalog.py` with `STRUCTURAL_EDGE_TYPES`, `AUDIT_EDGE_TYPES`, and `AGENT_TRAVERSAL_POLICY` constants per `contracts/edge-catalog.md`
- [x] T007 Export `graph_audit` models and new enum values from `src/models/__init__.py`
- [x] T008 Copy current `src/graph/builder.py` implementation to `src/graph/legacy_builder.py` unchanged for parity baseline (keep `GRAPH_BUILDER_VERSION` on legacy)
- [x] T009 [P] Add contract test `tests/contract/test_graph_materialize_boundary.py` asserting `graph.builder` and `graph.docling_graph_mapper` do not import `ingestion`, `retrieval`, or `evaluation` per `contracts/graph-materialize-boundary.md`
- [x] T010 [P] Add unit test `tests/unit/test_edge_catalog.py` validating audit whitelist excludes `TEMPORAL_TRANSITION` and `SEMANTIC_SIMILARITY`

**Checkpoint**: Enum and catalog tests pass; legacy builder preserved; import boundary test passes

---

## Phase 3: User Story 1 - Structurally Faithful Graph (Priority: P1) 🎯 MVP

**Goal**: docling-graph mapper emits full structural edge catalog and every XBRL fact instance; fail-closed per filing; `build_snapshot()` delegates to mapper

**Independent Test**: Materialize one 10-K + one 10-Q fixture; every table row and XBRL fact node has CONTAIN path to `doc-{accession}`; reading-order `NEXT` connects sections; broken filing excluded with `failure_reason`

### Implementation for User Story 1

- [x] T011 [US1] Implement `map_filing(doc: ParsedDocument) -> tuple[list[GraphNode], list[GraphEdge], FilingMaterializationResult]` in `src/graph/docling_graph_mapper.py` using docling-graph ER output bridged from `ParsedDocument` per `research.md` R1/R7
- [x] T012 [US1] Materialize **all** XBRL instances from `consolidate_xbrl_fact_rows` list output under `{doc}-xbrl-facts` as `CHUNK_XBRL_FACT` nodes in `src/graph/docling_graph_mapper.py` (remove graph use of `select_facts_for_index` cap)
- [x] T013 [US1] Map structural edges `CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES` in `src/graph/docling_graph_mapper.py` per `contracts/edge-catalog.md`; record unresolved footnote/cross-ref counts without traversable edges
- [x] T014 [US1] Enforce fail-closed per filing (zero sections, orphan evidence without CONTAIN chain) returning `FilingMaterializationResult.status=failed` in `src/graph/docling_graph_mapper.py`
- [x] T015 [US1] Refactor `src/graph/builder.py` to thin facade: `build_snapshot()` merges per-filing mapper results, sets `GRAPH_BUILDER_VERSION` to `docling-graph-mapper-1.0.0`, excludes failed filings
- [x] T016 [P] [US1] Add unit test `tests/unit/test_docling_graph_mapper.py` for containment chains, `NEXT` order, and fail-closed zero-section filing
- [x] T017 [P] [US1] Add unit test `tests/unit/test_docling_graph_mapper_xbrl.py` asserting multiple period contexts for same concept produce distinct nodes (no silent drop)
- [x] T018 [US1] Ensure `src/graph/registry.py` `build_issuer_snapshot()` calls new `build_snapshot()` only (no ingestion/parsing imports)
- [x] T019 [US1] Add integration test `tests/integration/test_graph_materialize_structural.py` on multi-accession AAPL fixtures verifying SC-002 zero orphans in published snapshot

**Checkpoint**: `uv run agent-query materialize --ticker AAPL` (fixtures) produces graph with uncapped XBRL facts and structural edges only from mapper

---

## Phase 4: User Story 2 - Issuer-Level Temporal and Semantic Linking (Priority: P2)

**Goal**: Multi-filing snapshots gain `TEMPORAL_TRANSITION` plus hybrid `SEMANTIC_SIMILARITY` (deterministic concept cross-period; optional thematic)

**Independent Test**: Materialize ≥4 quarterly + 1 annual fixture snapshot; consecutive periods linked by `TEMPORAL_TRANSITION`; same revenue concept across two periods linked by `SEMANTIC_SIMILARITY` with `link_method=deterministic`

### Implementation for User Story 2

- [x] T020 [US2] Implement `add_deterministic_concept_edges(snapshot)` in `src/graph/similarity.py` matching `xbrl_concept` + period metadata across filings per `research.md` R3
- [x] T021 [US2] Implement `add_thematic_edges(snapshot, config)` in `src/graph/similarity.py` gated by `USE_THEMATIC_GRAPH_LINKS` and `configs/graph_similarity.yaml`
- [x] T022 [US2] Wire deterministic + optional thematic similarity passes in `src/graph/builder.py` after per-filing structural merge
- [x] T023 [US2] Preserve or extend `TEMPORAL_TRANSITION` edge creation in `src/graph/builder.py` using 003 period ordering and `CorpusDefinition` metadata
- [x] T024 [P] [US2] Add unit test `tests/unit/test_similarity_deterministic.py` for cross-period revenue concept pairing and edge metadata (`link_method`, `concept_qname`)
- [x] T025 [US2] Add integration test `tests/integration/test_multi_filing_similarity.py` on multi-accession fixtures asserting temporal + deterministic similarity edges

**Checkpoint**: Multi-filing materialize includes cross-filing edges; thematic off by default in CI

---

## Phase 5: User Story 3 - Agent Traversability and Citation Paths (Priority: P3)

**Goal**: `GraphQueryAPI` returns structural shortest paths; retrieval trajectories record edge types along citation paths

**Independent Test**: Programmatic path from `doc-{accession}` to sample fact node uses only structural types; MLflow trajectory for `ask` includes `path_edge_types` per citation

### Implementation for User Story 3

- [x] T026 [US3] Implement `shortest_structural_path(snapshot, from_doc_id, to_node_id)` in `src/graph/query_api.py` using `edge_catalog.AUDIT_EDGE_TYPES` and hop budget default 6
- [x] T027 [US3] Extend `src/retrieval/orchestration/nodes/micro_extractor.py` to treat `GraphNodeType.CHUNK_XBRL_FACT` as numeric evidence alongside table/paragraph chunks
- [x] T028 [US3] Log `path_edge_types` and `path_node_ids` on citation records in `src/tracing/mlflow_langgraph.py` (or retrieval trajectory builder) per FR-014
- [x] T029 [US3] Ensure `src/retrieval/synthesis.py` passes through trajectory edge metadata without importing graph build modules
- [x] T030 [P] [US3] Add unit test `tests/unit/test_query_api_structural_path.py` for BFS path and disallowed edge type rejection

**Checkpoint**: Path query returns valid structural path for fixture fact; ask trajectory JSON includes edge types

---

## Phase 6: User Story 4 - Pilot Reachability Audit (Priority: P4)

**Goal**: Stratified audit ≥100 facts, N=6, ≥95% gate; JSON artifact on manifest; `graph-audit` CLI; materialize pipeline integration

**Independent Test**: `uv run agent-query graph-audit --ticker AAPL --snapshot-id <uuid>` writes `.reachability.json` with `audit_ready: true` on fixture pilot; manifest lists `audit_pass_rate`

### Implementation for User Story 4

- [x] T031 [US4] Implement `audit_snapshot_reachability()` and stratified sampler in `src/graph/reachability.py` per `contracts/reachability-audit.md` (≥60% XBRL / ≤40% table rows)
- [x] T032 [US4] Extend `src/graph/registry.py` to persist `{snapshot_id}.reachability.json` and manifest fields `audit_ready`, `audit_pass_rate`, `reachability_artifact`, `graph_builder_version`
- [x] T033 [US4] Implement `src/cli/commands/graph_audit.py` with `--ticker`, `--snapshot-id`; register subcommand in `src/cli/main.py`
- [x] T034 [US4] Wire `run_audit=True` default in `src/cli/corpus_pipeline.py` `run_materialize_pipeline()` after snapshot save; set `audit_ready` on index entry
- [x] T035 [P] [US4] Add contract test `tests/contract/test_reachability_audit_report.py` validating JSON schema fields from `data-model.md`
- [x] T036 [P] [US4] Add unit test `tests/unit/test_reachability.py` for hop budget, structural-only BFS, and pass_rate threshold
- [x] T037 [US4] Add integration test `tests/integration/test_graph_audit_gate.py` asserting ≥95% pass on AAPL fixture snapshot or documenting waiver path

**Checkpoint**: Materialize produces reachability artifact; sub-95% sets `audit_ready=false` without blocking ask (003 stale pattern)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Legacy parity, default cutover, MLflow artifacts, docs validation

- [x] T038 [P] Add integration test `tests/integration/test_graph_builder_parity.py` comparing `legacy_builder` vs docling-graph mapper on AAPL fixtures (±5% structural counts, 100% XBRL concept+period key coverage) per `research.md` R6
- [x] T039 Switch default publish path to docling-graph in `src/graph/builder.py` (env `GRAPH_BUILDER=legacy` escape hatch only); document in `README.md`
- [x] T040 [P] Log `reachability.json` MLflow artifact and tags `audit_ready`, `audit_pass_rate` in `src/cli/corpus_pipeline.py` materialize runs
- [x] T041 Validate `specs/004-docling-graph-materialization/quickstart.md` steps 1–5 on fixture corpus and fix doc gaps

**Checkpoint**: Parity green; CI uses docling-graph default; quickstart reproducible

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP**; blocks US2–US4 functionally
- **US2 (Phase 4)**: Depends on US1 structural snapshot
- **US3 (Phase 5)**: Depends on US1 (`query_api` needs nodes); can parallel with US2 after US1
- **US4 (Phase 6)**: Depends on US1 + US3 (`shortest_structural_path`); should follow US3
- **Polish (Phase 7)**: Depends on US1–US4 complete

### User Story Dependencies

```text
Foundational → US1 (P1) → US2 (P2)
                      ↘ US3 (P3) → US4 (P4) → Polish (parity + cutover)
```

- **US1**: No dependency on US2–US4
- **US2**: Requires US1 mapper and `build_snapshot` merge
- **US3**: Requires US1 nodes; uses `edge_catalog` from Foundational
- **US4**: Requires US1 snapshot + US3 path helper (recommended)

### Parallel Opportunities

- **Phase 1**: T001 ∥ T002
- **Phase 2**: T009 ∥ T010 (after T004–T008)
- **US1**: T016 ∥ T017 (after T011–T015)
- **US2**: T024 parallel with T025 prep after T020–T023
- **US3**: T030 after T026
- **US4**: T035 ∥ T036 (after T031)
- **Polish**: T038 ∥ T040

### Parallel Example: User Story 1

```bash
# After T011–T015 complete:
uv run pytest tests/unit/test_docling_graph_mapper.py tests/unit/test_docling_graph_mapper_xbrl.py -q
```

### Parallel Example: User Story 4

```bash
# Contract + unit audit tests together:
uv run pytest tests/contract/test_reachability_audit_report.py tests/unit/test_reachability.py -q
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1)
3. **STOP and VALIDATE**: `materialize` on AAPL fixtures; manual CONTAIN path check for sample XBRL fact
4. Demo `ask` with scoped evidence (003 binding still works)

### Incremental Delivery

1. US1 → structural multi-filing graphs, uncapped XBRL
2. US2 → cross-period similarity + temporal edges
3. US3 → auditable citation paths in trajectories
4. US4 → 95% reachability gate + `graph-audit` CLI
5. Polish → parity proof, default cutover, MLflow artifacts

### Suggested MVP Scope

**User Story 1 only** (T001–T019): Delivers docling-graph mapper, fail-closed materialize, and uncapped XBRL nodes — unblocks correct multi-period revenue without audit gate yet.

---

## Notes

- Do **not** modify `src/ingestion/` or parsing contracts except consuming existing `ParsedDocument` JSON
- Reachability audit MUST NOT traverse `SEMANTIC_SIMILARITY` or `TEMPORAL_TRANSITION` (SC-001)
- Thematic similarity remains **off** in CI (`configs/graph_similarity.yaml`)
- Commit after each phase checkpoint; use `[Spec Kit]` prefix for spec-kit commits
