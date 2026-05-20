---
description: "Task list for multi-filing issuer corpus and temporal snapshots"
---

# Tasks: Multi-Filing Issuer Corpus & Temporal Snapshots

**Input**: Design documents from `specs/003-multi-filing-corpus/`

**Prerequisites**: `001-sec-disclosure-rag` and `002-live-disclosure-cli` implemented; plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Unit, contract, and integration tests included per plan (corpus cap, binding manifests, layer boundaries).

**Organization**: Tasks grouped by user story (P1 → P2 → P3) per spec.md. Extends 002 ingestion/cache and existing multi-doc `graph.builder` — no parallel fetch stack.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/ingestion/`, `src/graph/`, `src/retrieval/`, `src/cli/`, `src/models/`, `src/parsing/`
- Additive: `src/ingestion/corpus.py`, `src/graph/registry.py`, `src/retrieval/temporal.py`, `src/cli/corpus_pipeline.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Fixtures, config, and docs for multi-filing development

- [x] T001 [P] Add second fixture accession under `tests/fixtures/sec_downloads/AAPL/{accession}/` with valid `manifest.json` for multi-filing integration tests
- [x] T002 [P] Add `configs/corpus.yaml` with `max_filings: 12`, `trailing_10k: 1`, `trailing_10q: 4` defaults
- [x] T003 Document multi-filing storage (`data/parsed/{ticker}/{accession}.json`, `data/graphs/{issuer}/index.json`) in `README.md`

**Checkpoint**: Fixture corpus has ≥2 accessions; config loadable from tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed corpus models and import boundaries — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T004 Add corpus Pydantic models (`CorpusDefinition`, `CorpusMember`, `CorpusMaterializationJob`, `FiscalPeriodLabel`, `FilingBinding`, `SnapshotScopeManifest`, `IssuerSnapshotIndex`) in `src/models/corpus.py` per `data-model.md`
- [x] T005 Extend `CLIAskRequest` and `CLIAskResult` in `src/models/ingestion.py` with `temporal_scope`, `corpus_definition`, `reuse_snapshot_id`, `snapshot_scope` fields
- [x] T006 Export corpus models from `src/models/__init__.py`
- [x] T007 [P] Add `CorpusCapExceededError` and definition validation helpers in `src/ingestion/corpus.py`
- [x] T008 [P] Add contract test `tests/contract/test_corpus_imports.py` asserting `ingestion.corpus` does not import `graph`, `retrieval`, or `evaluation`
- [x] T009 [P] Add unit test `tests/unit/test_corpus_models.py` for cap rejection when resolved members exceed `max_filings`

**Checkpoint**: Model validation tests pass; import boundary test passes

---

## Phase 3: User Story 1 - Multi-Filing Corpus Snapshot (Priority: P1) 🎯 MVP

**Goal**: Fetch/cache multiple 10-K/10-Q filings for one issuer and publish a versioned multi-filing `GraphSnapshot` with registry index

**Independent Test**: `uv run agent-query materialize --ticker AAPL` produces `data/graphs/AAPL/{snapshot_id}.graphml`, `index.json` listing ≥2 filings with period/accession metadata (fixture or live EDGAR)

### Implementation for User Story 1

- [x] T010 [US1] Implement `list_recent_filings()` in `src/ingestion/edgar_client.py` using EDGAR `submissions.recent` with dedupe by fiscal period
- [x] T011 [US1] Implement `resolve_corpus_members(definition: CorpusDefinition)` in `src/ingestion/corpus.py` for `default_trailing`, `explicit_accessions`, and `date_range` modes
- [x] T012 [US1] Implement `materialize_corpus_members()` in `src/ingestion/corpus.py` batching `fetch_filing()` per member with per-filing status tracking
- [x] T013 [US1] Export `list_recent_filings`, `materialize_corpus`, and `CorpusCapExceededError` from `src/ingestion/__init__.py` per `contracts/corpus-boundary.md`
- [x] T014 [P] [US1] Add unit test `tests/unit/test_list_recent_filings.py` for fixture and dedupe behavior
- [x] T015 [P] [US1] Add unit test `tests/unit/test_corpus_materialize.py` for cap exceeded and partial failure recording
- [x] T016 [US1] Extend `write_parsed_document()` in `src/parsing/sec_download_adapter.py` to persist `data/parsed/{ticker}/{accession}.json` per filing
- [x] T017 [US1] Implement `build_issuer_snapshot()` in `src/graph/registry.py` wrapping `graph.builder.build_snapshot` and `graph.store.save_snapshot`
- [x] T018 [US1] Implement `register_snapshot()`, `get_latest_snapshot()`, and `IssuerSnapshotIndex` persistence in `src/graph/registry.py` at `data/graphs/{issuer}/index.json`
- [x] T019 [US1] Implement `run_materialize_pipeline()` in `src/cli/corpus_pipeline.py` orchestrating corpus fetch → parse each member → `build_issuer_snapshot` → register
- [x] T020 [US1] Implement `src/cli/commands/materialize.py` with `--ticker`, `--cik`, `--force-refresh`, corpus override flags; wire subcommand in `src/cli/main.py`
- [x] T021 [P] [US1] Add integration test `tests/integration/test_corpus_materialize.py` using multi-accession fixtures

**Checkpoint**: Materialize command succeeds on fixtures; snapshot manifest lists multiple `filing_refs` with temporal edges in graph

---

## Phase 4: User Story 2 - Temporal Scope in Queries (Priority: P2)

**Goal**: Pre-materialize default corpus on ask; bind fiscal-period subset per query; extend snapshot when required period is missing; structured benchmark scope support

**Independent Test**: `agent-query ask` with `--anchor prior-quarter` binds correct accession from multi-filing snapshot; benchmark case with `temporal_scope` JSON resolves same binding

### Implementation for User Story 2

- [x] T022 [US2] Implement `fiscal_period_label()` from `FilingRef` in `src/retrieval/temporal.py` (issuer fiscal periods only)
- [x] T023 [US2] Implement `resolve_temporal_scope()` for structured anchors and explicit periods in `src/retrieval/temporal.py`
- [x] T024 [US2] Implement `bind_filings_for_query()` in `src/retrieval/temporal.py` returning `FilingBinding` with resolution notes
- [x] T025 [US2] Implement default corpus load-or-materialize and snapshot extend path in `src/cli/corpus_pipeline.py` `run_ask_pipeline()`
- [x] T026 [US2] Refactor `src/cli/pipeline.py` to delegate `run_ask_pipeline()` to `src/cli/corpus_pipeline.py`
- [x] T027 [US2] Extend `src/cli/commands/ask.py` with `--anchor`, `--period`, `--compare`, `--snapshot-id`, and explicit-scope conflict validation (FR-009c)
- [x] T028 [US2] Pass pre-bound `filing_set` and `binding_manifest` via `QueryRequest.metadata` in `src/retrieval/service.py` initial LangGraph state
- [x] T029 [US2] Update `macro_router` in `src/retrieval/orchestration/nodes/macro_router.py` to skip LLM filing selection when `filing_set` is pre-populated
- [x] T030 [P] [US2] Add unit test `tests/unit/test_temporal_binding.py` for latest_annual, prior_quarter, and comparison pairs on fixture manifest
- [x] T031 [P] [US2] Add integration test `tests/integration/test_multi_period_ask.py` for CLI structured scope vs benchmark structured scope parity

**Checkpoint**: Ask binds subset without full re-materialize; missing period triggers new snapshot version

---

## Phase 5: User Story 3 - Analyst-Visible Snapshot Transparency (Priority: P3)

**Goal**: Snapshot scope summary on every ask; stale-snapshot warnings; MLflow `binding_manifest.json`; benchmark binding assertions

**Independent Test**: Period-comparison ask prints snapshot scope with accessions; stale run lists `newer_available`; MLflow run contains `binding_manifest.json` artifact

### Implementation for User Story 3

- [x] T032 [US3] Implement `probe_stale_filings()` in `src/graph/registry.py` comparing snapshot max `filed_at` to `list_recent_filings()`
- [x] T033 [US3] Build `SnapshotScopeManifest` (bound filings, stale flag, newer_available) in `src/cli/corpus_pipeline.py` and set on `CLIAskResult.snapshot_scope`
- [x] T034 [US3] Render human-readable **Snapshot scope** section and JSON fields in `src/cli/commands/ask.py` per `contracts/snapshot-scope-manifest.md`
- [x] T035 [US3] Log `binding_manifest.json` MLflow artifact and params (`bound_accessions`, `stale_snapshot`) in `src/cli/corpus_pipeline.py` or `src/tracing/mlflow_langgraph.py`
- [x] T036 [US3] Require `temporal_scope` on benchmark items and fail setup when missing in `src/evaluation/runner.py` / dataset adapters per `contracts/temporal-scope.md`
- [x] T037 [P] [US3] Add contract test `tests/contract/test_snapshot_scope_manifest.py` validating schema and SC-004 required fields
- [x] T038 [P] [US3] Add integration test `tests/integration/test_corpus_binding.py` asserting expected vs actual accessions for fixture benchmark cases

**Checkpoint**: 100% successful ask runs include snapshot scope; stale queries warn without blocking

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Concurrency, partial failures, documentation, regression sweep

- [x] T039 [P] Add per-issuer materialize lock file in `src/graph/registry.py` or `src/ingestion/corpus.py` to prevent concurrent snapshot corruption
- [x] T040 Handle partial corpus member failures (exclude failed filings, block queries depending on missing members) in `src/ingestion/corpus.py` and `src/cli/corpus_pipeline.py`
- [x] T041 [P] Align `specs/003-multi-filing-corpus/quickstart.md` with implemented CLI flags
- [x] T042 [P] Update `README.md` with `agent-query materialize` and multi-period `ask` examples
- [x] T043 Run full `pytest` suite and fix layer import or binding regressions

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Setup (T001–T003) → Foundational (T004–T009) → US1 (T010–T021) → US2 (T022–T031) → US3 (T032–T038) → Polish (T039–T043)
```

### User Story Dependencies

```text
US1 (P1) ──► US2 (P2) ──► US3 (P3)
```

- **US2** requires US1 (multi-filing snapshot + registry exist before temporal bind)
- **US3** requires US2 (binding pipeline exists before scope manifest + stale probe on ask)

### Within Each User Story

- Foundational models before ingestion/graph/cli work
- `list_recent_filings` before `resolve_corpus_members`
- `graph/registry.py` before `corpus_pipeline.py`
- `temporal.py` before ask pipeline refactor
- Contract/integration tests after core implementation in each story

### Parallel Opportunities

- **Phase 1**: T001, T002 in parallel
- **Phase 2**: T007, T008, T009 in parallel after T004
- **Phase 3**: T014, T015 parallel after T012; T021 after T019
- **Phase 4**: T030, T031 parallel after T029
- **Phase 5**: T037, T038 parallel after T033
- **Phase 6**: T039, T041, T042 in parallel

---

## Parallel Example: User Story 1

```bash
# After T012:
# Terminal A: T014 tests/unit/test_list_recent_filings.py
# Terminal B: T015 tests/unit/test_corpus_materialize.py

# After T018:
# T016 src/parsing/sec_download_adapter.py (parsed path convention)
# T017 src/graph/registry.py (build_issuer_snapshot)
```

---

## Parallel Example: User Story 2

```bash
# After T024:
# T022–T024 src/retrieval/temporal.py (can split helpers if needed)
# T030 tests/unit/test_temporal_binding.py (after T023)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2 (T001–T009)
2. Complete Phase 3 (T010–T021): `agent-query materialize --ticker AAPL`
3. **STOP and VALIDATE**: `index.json` + multi-filing graph manifest without running ask
4. Demo corpus materialization before temporal binding or scope UI

### Incremental Delivery

1. Setup + Foundational → typed corpus contracts
2. US1 → multi-filing snapshot + materialize CLI (MVP)
3. US2 → temporal bind + multi-period ask
4. US3 → snapshot scope transparency + benchmark binding tests
5. Polish → locks, partial failure, docs

### Suggested MVP Scope

**User Story 1** (T001–T021): Issuer corpus materialization and versioned multi-filing graph only.

---

## Task Summary

| Phase | Task IDs | Count |
|-------|----------|-------|
| Setup | T001–T003 | 3 |
| Foundational | T004–T009 | 6 |
| US1 (P1) | T010–T021 | 12 |
| US2 (P2) | T022–T031 | 10 |
| US3 (P3) | T032–T038 | 7 |
| Polish | T039–T043 | 5 |
| **Total** | **T001–T043** | **43** |

**Parallel opportunities**: 14 tasks marked `[P]`  
**Independent test criteria**: Documented per user story phase header

---

## Notes

- Reuse `fetch_filing()` for every corpus member — do not duplicate download logic (plan constraint)
- `graph.builder.build_snapshot` already supports multiple documents; 003 changes orchestration only
- Benchmarks MUST use structured `temporal_scope`; CLI NL resolution is optional per spec clarifications
- Commit after each phase checkpoint; run `uv run agent-query materialize` before multi-period ask validation
