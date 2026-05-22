---
description: "Task list for supplementary HTML narrative and intent router (005)"
---

# Tasks: Supplementary SEC HTML Narrative Ingestion

**Input**: Design documents from `specs/005-html-narrative-supplement/`

**Prerequisites**: `004-docling-graph-materialization` merged; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit, contract, and integration tests per plan (HTML ingest gate, parse merge, intent router trace, source-tagged citations).

**Organization**: Tasks grouped by user story (P1 → P4) per spec.md. Extends 002/003/004 pipelines — **no** XBRL-primary contract breakage.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/ingestion/`, `src/parsing/`, `src/graph/`, `src/retrieval/orchestration/`, `src/tracing/`, `src/cli/`, `src/models/`
- New: `src/ingestion/html_narrative.py`, `src/parsing/html_narrative.py`, `src/retrieval/orchestration/nodes/intent_router.py`
- Config: `configs/html_narrative.yaml`, `configs/intent_router.yaml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config files, dependency, operator docs

- [x] T001 [P] Add `configs/html_narrative.yaml` with Item heading patterns, inline-vs-fallback heuristics, and default `html_narrative_enabled: true` per `research.md` R2
- [x] T002 [P] Add `configs/intent_router.yaml` with LLM prompt template, timeout, and keyword fallback lexicons per `research.md` R5
- [x] T003 Add `beautifulsoup4` to `pyproject.toml` and refresh `uv.lock` via `uv lock` per `research.md` R2
- [x] T004 Document HTML narrative default materialize, `--skip-html-narrative`, and intent router trace fields in `README.md` linking `specs/005-html-narrative-supplement/quickstart.md`

**Checkpoint**: Configs load in tests; README references 005 quickstart

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared enums and typed models for source tags and router trace — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T005 Add `EvidenceSourceType`, `QueryIntent`, `IntentSource`, `SourceBias`, `RouterFallbackReason`, `NarrativeSectionKind`, `HtmlNarrativeStatus` to `src/models/enums.py` per `data-model.md`
- [x] T006 Extend `SectionBlock` with `source_type` and `narrative_kind` in `src/models/filing.py` per `contracts/parsed-document-merge.md`
- [x] T007 Extend `ParsedDocument` with `html_narrative_status` and `html_artifact_path` in `src/models/parsing.py`
- [x] T008 Add `IntentRouterTrace` and extend `EvidenceChunk` with `source_type`, `accession`, `section_id` in `src/models/query.py` per `data-model.md`
- [x] T009 Extend `TrajectoryRecord` with `intent_router: IntentRouterTrace | None` in `src/models/query.py` per `contracts/intent-router-trace.md`
- [x] T010 Export new enums and models from `src/models/__init__.py`
- [x] T011 [P] Add contract test `tests/contract/test_html_ingest_boundary.py` asserting `ingestion.html_narrative` does not import `parsing`, `graph`, or `retrieval` per `contracts/html-narrative-ingest.md`
- [x] T012 [P] Add unit test `tests/unit/test_evidence_source_enums.py` validating enum values match spec router trace table

**Checkpoint**: Model tests pass; layer import boundary test passes

---

## Phase 3: User Story 1 - Supplementary HTML Fetch (Priority: P1) 🎯 MVP

**Goal**: Paired HTML narrative ingest for XBRL-complete accessions; inline iXBRL preferred; `.htm` fallback; manifest HTML status independent of XBRL

**Independent Test**: Given cached XBRL accession, run supplementary ingest; manifest lists HTML role and path; HTML-only request for accession without XBRL fails with explicit error

### Implementation for User Story 1

- [x] T013 [US1] Implement `resolve_narrative_html()` in `src/ingestion/html_narrative.py` (inline package first, EDGAR `.htm` fallback) per `contracts/html-narrative-ingest.md`
- [x] T014 [US1] Implement `ingest_html_narrative()` with FR-001 gate (reject without complete XBRL package) in `src/ingestion/html_narrative.py`
- [x] T015 [P] [US1] Add inline HTML discovery helper in `src/ingestion/package_utils.py` and `src/ingestion/edgar_xbrl.py` per `research.md` R1
- [x] T016 [US1] Extend cache manifest serialization with `html_narrative_status`, `html_artifact_role`, `html_artifact_relpath` in `src/ingestion/cache_manager.py` (or manifest writer used by fetch)
- [x] T017 [US1] Wire `ingest_html_narrative()` after successful XBRL fetch in `src/ingestion/__init__.py` / `fetch_filing` path when HTML not skipped
- [x] T018 [US1] Reject orphan HTML-only cache creation in `src/ingestion/validators.py` per FR-001
- [x] T019 [P] [US1] Add unit test `tests/unit/test_html_narrative_ingest.py` for inline resolution, fallback path, and XBRL-missing rejection
- [x] T020 [US1] Extend `tests/integration/test_cache_roundtrip.py` (or add `tests/integration/test_html_narrative_ingest.py`) asserting paired ingest on AAPL fixture without invalidating XBRL manifest

**Checkpoint**: Fixture accession has HTML artifact + manifest fields; HTML-only ingest fails closed

---

## Phase 4: User Story 2 - Parse and Tag Narrative Sections (Priority: P2)

**Goal**: Extract MD&A, risk factors, business description from HTML; merge into single `ParsedDocument` JSON with `source_type=HTML`

**Independent Test**: Parse 10-K fixture; `data/parsed/{ticker}/{accession}.json` contains both XBRL and HTML sections; XBRL sections unchanged

### Implementation for User Story 2

- [x] T021 [US2] Implement `extract_narrative_sections()` in `src/parsing/html_narrative.py` using BS4 + `configs/html_narrative.yaml` heading map per `research.md` R2
- [x] T022 [US2] Implement `merge_html_into_document()` with `html-` section ID prefix and content hash recompute in `src/parsing/html_narrative.py` per `contracts/parsed-document-merge.md`
- [x] T023 [US2] Hook HTML extract-and-merge after XBRL parse in `src/parsing/sec_download_adapter.py` (`parse_from_cache` or dedicated `parse_with_narrative`)
- [x] T024 [US2] Extend `src/parsing/validators.py` to validate merged document (XBRL sections retain default `source_type`, HTML sections required tags)
- [x] T025 [P] [US2] Add unit test `tests/unit/test_html_narrative_parse.py` for Item 7/1/1A section extraction on fixture HTML
- [x] T026 [P] [US2] Add unit test `tests/unit/test_parsed_document_merge.py` asserting single JSON artifact and no XBRL section overwrite
- [x] T027 [US2] Add contract test `tests/contract/test_parsed_document_merge_contract.py` enforcing no sidecar `*-html.json` per `contracts/parsed-document-merge.md`

**Checkpoint**: `write_parsed_document` emits merged parse; malformed HTML records `html_narrative_status=failed` without breaking XBRL parse

---

## Phase 5: User Story 3 - Unified Graph with Source-Aware Evidence (Priority: P3)

**Goal**: Graph nodes carry `source_type`; materialize runs HTML by default; LLM intent router + keyword fallback biases evidence ranking

**Independent Test**: Materialize snapshot with HTML parse; graph nodes include `properties.source_type=HTML`; numeric ask prioritizes XBRL; qualitative ask includes HTML chunk when available

### Implementation for User Story 3

- [x] T028 [US3] Set `GraphNode.properties["source_type"]` and optional `narrative_kind` from `SectionBlock` in `src/graph/docling_graph_mapper.py`
- [x] T029 [US3] Call HTML narrative parse path in `src/cli/corpus_pipeline.py` materialize loop (default on; respect skip flag)
- [x] T030 [US3] Add `--skip-html-narrative` flag to materialize CLI in `src/cli/main.py` and plumb to `run_materialize_pipeline()` per FR-010
- [x] T031 [US3] Implement `intent_router()` with LLM JSON classify in `src/retrieval/orchestration/nodes/intent_router.py` per `contracts/intent-router-trace.md`
- [x] T032 [US3] Implement `classify_intent_keywords()` fallback in `src/retrieval/orchestration/nodes/intent_router.py` loading `configs/intent_router.yaml`
- [x] T033 [US3] Insert `intent_router` node between `macro_router` and `meso_router` in `src/retrieval/orchestration/graph.py`
- [x] T034 [US3] Add `intent_trace` to `src/retrieval/orchestration/state.py`
- [x] T035 [US3] Apply source-bias scoring in `src/retrieval/orchestration/nodes/micro_extractor.py` from `state["intent_trace"].source_bias_applied` per `research.md` R7
- [x] T036 [US3] Boost HTML section labels in `src/retrieval/orchestration/nodes/meso_router.py` when `query_intent` is `qualitative` or `hybrid`
- [x] T037 [P] [US3] Add unit test `tests/unit/test_intent_router.py` for LLM path, invalid label fallback, and `USE_MOCK_LLM=1` keyword path
- [x] T038 [P] [US3] Add unit test `tests/unit/test_micro_extractor_source_bias.py` for xbrl_primary vs html_primary ranking
- [x] T039 [US3] Add integration test `tests/integration/test_graph_html_nodes.py` asserting HTML-tagged nodes reachable from document root on fixture snapshot

**Checkpoint**: `materialize` produces HTML graph nodes; `ask` qualitative query returns HTML-biased evidence when narrative indexed

---

## Phase 6: User Story 4 - Source-Tagged Citations (Priority: P4)

**Goal**: CLI and JSON citations display `source_type`; trajectory evidence list includes source tags

**Independent Test**: Ask with mixed evidence; every citation shows XBRL or HTML; HTML-only answer has no false XBRL numeric labels

### Implementation for User Story 4

- [x] T040 [US4] Populate `EvidenceChunk.source_type`, `accession`, `section_id` from graph node properties in `src/retrieval/orchestration/nodes/micro_extractor.py` per `contracts/source-tagged-citations.md`
- [x] T041 [US4] Render `source_type` in citation output in `src/retrieval/synthesis.py` and `src/retrieval/cli.py` (JSON + text modes) per FR-008
- [x] T042 [US4] Extend `src/contracts/query.py` / ask response schema docs if typed response wrapper exists
- [x] T043 [P] [US4] Add unit test `tests/unit/test_citation_source_type.py` for synthesis/CLI citation serialization
- [x] T044 [US4] Add integration test `tests/integration/test_ask_html_citation.py` for qualitative MD&A query with ≥1 HTML citation on fixture corpus (SC-001 pilot subset)

**Checkpoint**: SC-003 — 100% of cited successful asks show `source_type` on every citation

---

## Phase 7: User Story 5 - Router Observability in Agent Tracing (Priority: P4)

**Goal**: `IntentRouterTrace` on trajectory and MLflow; structured params + `intent_router.json` artifact; fallback reason when keyword path used

**Independent Test**: Inspect `trajectory.json` and MLflow run after ask; required router fields present; mock LLM shows `intent_source=keyword_fallback` + `router_fallback_reason`

### Implementation for User Story 5

- [x] T045 [US5] Map `state["intent_trace"]` → `TrajectoryRecord.intent_router` in `src/tracing/mlflow_langgraph.py` `build_trajectory_from_state()` per FR-013
- [x] T046 [US5] Log MLflow params `query_intent`, `intent_source`, `source_bias_applied`, and optional `router_fallback_reason` in `src/tracing/mlflow_langgraph.py` / `src/retrieval/service.py` per FR-015
- [x] T047 [US5] Log artifact `intent_router.json` (full `IntentRouterTrace`) alongside `trajectory.json` in `src/tracing/mlflow_langgraph.py`
- [x] T048 [US5] Ensure `macro_router` does not overwrite `query_intent` on trajectory (document route only) in `src/retrieval/orchestration/nodes/macro_router.py`
- [x] T049 [P] [US5] Add unit test `tests/unit/test_intent_router_trace.py` for required fields on LLM and fallback paths (SC-006)
- [x] T050 [US5] Add contract test `tests/contract/test_trajectory_router_fields.py` validating stable `intent_router` schema for eval loader
- [x] T051 [US5] Extend `src/evaluation/metrics/trajectory.py` (optional) to score presence of `intent_router` fields for benchmark runs

**Checkpoint**: SC-006/SC-007 — pilot audit can determine intent and fallback from artifacts alone

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Reachability stratification, benchmarks, docs, end-to-end validation

- [x] T052 [P] Extend `src/graph/reachability.py` stratification to include HTML prose chunks where configured per US3 acceptance scenario 5
- [x] T053 [P] Tag pilot benchmark items with `requires_narrative: true` in evaluation dataset config (≥10 items) per `research.md` R8
- [x] T054 Run and fix gaps from `specs/005-html-narrative-supplement/quickstart.md` steps 1–7 on AAPL fixture corpus
- [x] T055 [P] Add contract test `tests/contract/test_layer_boundaries_005.py` asserting parsing does not import retrieval and graph does not import `html_narrative` ingest network calls
- [x] T056 Update `.cursor/rules/specify-rules.mdc` if CLI flags or storage paths changed during implementation

**Checkpoint**: Quickstart reproducible; layer contracts green; ready for `/speckit-implement`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP** ingest gate
- **US2 (Phase 4)**: Depends on US1 (needs HTML artifact in cache)
- **US3 (Phase 5)**: Depends on US2 (merged `ParsedDocument`); intent router can be built in parallel with graph mapper after Foundational
- **US4 (Phase 6)**: Depends on US3 (`micro_extractor` source tags)
- **US5 (Phase 7)**: Depends on US3 (`intent_router` node); should follow US4 for end-to-end ask validation
- **Polish (Phase 8)**: Depends on US1–US5

### User Story Dependencies

```text
Foundational → US1 (P1) → US2 (P2) → US3 (P3) → US4 (P4) → US5 (P4) → Polish
```

- **US1**: No dependency on US2–US5
- **US2**: Requires US1 HTML artifact
- **US3**: Requires US2 merged parse; delivers graph + router + ranking
- **US4**: Requires US3 evidence extraction
- **US5**: Requires US3 intent router; completes observability contract

### Parallel Opportunities

- **Phase 1**: T001 ∥ T002
- **Phase 2**: T011 ∥ T012 (after T005–T010)
- **US1**: T015 ∥ T019 (after T013–T014)
- **US2**: T025 ∥ T026 (after T021–T024)
- **US3**: T037 ∥ T038 (after T031–T036); T028 ∥ T031 after Foundational (different files)
- **US4**: T043 after T040–T042
- **US5**: T049 ∥ T050 (after T045–T048)
- **Polish**: T052 ∥ T053

### Parallel Example: User Story 3

```bash
# Graph mapper and intent router in parallel after US2 merge tests pass:
# Task T028 docling_graph_mapper.py
# Task T031 intent_router.py
uv run pytest tests/unit/test_intent_router.py tests/unit/test_docling_graph_mapper.py -q
```

### Parallel Example: User Story 5

```bash
uv run pytest tests/unit/test_intent_router_trace.py tests/contract/test_trajectory_router_fields.py -q
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1)
3. **STOP and VALIDATE**: Paired HTML ingest on AAPL fixture; manifest `html_narrative_status=success`
4. US2+ can proceed for full narrative retrieval value

### Incremental Delivery

1. US1 → supplementary HTML in cache
2. US2 → merged `ParsedDocument`
3. US3 → graph `source_type` + intent router + biased retrieval
4. US4 → citation labels for analysts
5. US5 → MLflow router trace for audit/benchmarks
6. Polish → reachability + benchmark tags + quickstart

### Suggested MVP Scope

**User Stories 1–2** (T001–T027): Delivers ingest + merged parse — unblocks graph/retrieval work without full ask observability.

**Minimum ask demo**: Through **US5** (T001–T051) for SC-006 router trace on qualitative queries.

---

## Notes

- Do **not** replace XBRL-primary parse; HTML is supplementary only (constitution II)
- `query_intent` on trajectory is **canonical** from `intent_router`; macro plan is filing/temporal only
- Keyword fallback MUST NOT label `intent_source=llm` (FR-014)
- Commit after each phase checkpoint; use `[Spec Kit]` prefix for spec-kit commits
