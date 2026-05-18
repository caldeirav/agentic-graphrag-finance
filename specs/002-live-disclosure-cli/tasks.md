---
description: "Task list for live disclosure ingestion and agent-query CLI"
---

# Tasks: Live Regulatory Disclosure Ingestion & Developer CLI

**Input**: Design documents from `specs/002-live-disclosure-cli/`

**Prerequisites**: `001-sec-disclosure-rag` implemented; plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Contract and integration tests included; CI uses `SEC_API_KEY=test-mock` and mocked sec-api responses.

**Organization**: Tasks grouped by user story (P1 → P2 → P3) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps)
- **[USn]**: User story label

## Path Conventions

- Additive packages: `src/ingestion/`, `src/cli/`
- Extends: `src/parsing/`, `src/models/`, `pyproject.toml`

---

## Phase 1: Setup (Workspace & Dependencies)

**Purpose**: Phase P0 — `sec-api`, `SEC_API_KEY`, `agent-query` entrypoint

- [x] T001 Add `sec-api` and `typer` via `uv add sec-api typer` and commit updated `uv.lock`
- [x] T002 Add `SEC_API_KEY` and `SEC_API_REQUESTS_PER_SECOND` to `.env.example` with comments
- [x] T003 Register `agent-query = "cli.main:app"` in `pyproject.toml` `[project.scripts]` and add `src/ingestion`, `src/cli` to hatch wheel packages
- [x] T004 [P] Scaffold `src/ingestion/` package (`__init__.py`, `settings.py` stub) and `src/cli/` (`__init__.py`, `main.py` stub, `commands/`)
- [x] T005 [P] Create `data/raw/sec_downloads/.gitkeep` and `data/cache/sec-api/.gitkeep`; document layout in `README.md`
- [x] T006 [P] Add `configs/ingestion.yaml` for downloads root and rate-limit defaults
- [x] T007 Update CI in `.github/workflows/ci.yml` to set `SEC_API_KEY=test-mock` for ingestion/cli test jobs
- [x] T008 [P] Add `tests/ingestion/` and `tests/cli/` package init files

**Checkpoint**: `uv sync --locked` succeeds; `uv run agent-query --help` runs (empty subcommands OK)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared ingestion types and settings — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T009 Add ingestion Pydantic models (`FilingResolution`, `XBRLArtifact`, `XBRLArtifactManifest`, `CacheEntry`, `FetchJob`, `IssuerIdentifierInput`) in `src/models/ingestion.py` and export from `src/models/__init__.py`
- [x] T010 Implement `src/ingestion/settings.py` with `require_sec_api_key()` and `IngestionSettings` via env (`SEC_API_KEY`, `SEC_DOWNLOADS_ROOT`)
- [x] T011 Implement `get_sec_client()` factory wrapping sec-api SDK in `src/ingestion/sec_client.py` (skeleton only, no fetch yet)
- [x] T012 [P] Add `tests/conftest_sec_api.py` with mock sec-api fixtures and sample `manifest.json` under `tests/fixtures/sec_downloads/`
- [x] T013 [P] Add contract test `tests/contract/test_ingestion_imports.py` (ingestion ↛ graph, retrieval, evaluation)
- [x] T014 [P] Add unit test `tests/unit/test_ingestion_settings.py` for missing-key error message

**Checkpoint**: `require_sec_api_key()` fails clearly without env; import boundary tests pass

---

## Phase 3: User Story 1 - Dynamic XBRL Fetch & Resolve (Priority: P1) 🎯 MVP

**Goal**: Resolve ticker/CIK/accession → XBRL artifact manifest via sec-api; download raw files to `sec_downloads/`

**Independent Test**: `fetch_filing(ticker="AAPL", form_type="10-K")` returns `CacheEntry` with complete manifest and `.xml`/`.xsd` files on disk

### Implementation for User Story 1

- [x] T015 [P] [US1] Implement ticker→CIK resolution with `data/cache/sec-api/ticker_map.json` cache in `src/ingestion/sec_client.py`
- [x] T016 [US1] Implement latest-filing query for 10-K/10-Q by CIK, ticker, or accession in `src/ingestion/sec_client.py`
- [x] T017 [US1] Implement `resolve_identifier()` public API in `src/ingestion/__init__.py` per `contracts/ingestion-boundary.md`
- [x] T018 [US1] Implement `xbrl_downloader.py` to list and download instance/taxonomy artifacts via sec-api
- [x] T019 [US1] Write `manifest.json` (`XBRLArtifactManifest`) under `data/raw/sec_downloads/{ticker}/{accession}/`
- [x] T020 [US1] Implement `validators.py` instance + taxonomy completeness checks in `src/ingestion/validators.py`
- [x] T021 [US1] Expose `fetch_filing()` orchestrating resolve → download → validate in `src/ingestion/__init__.py`
- [x] T022 [P] [US1] Add unit tests for resolution failures (unknown ticker) in `tests/ingestion/test_sec_client.py`
- [x] T023 [P] [US1] Add integration test with mocked sec-api responses in `tests/ingestion/test_xbrl_downloader.py`

**Checkpoint**: Programmatic fetch works against mocks; live fetch verified manually with real `SEC_API_KEY`

---

## Phase 4: User Story 2 - Local Disclosures Asset Cache (Priority: P2)

**Goal**: Hash-based cache hits, atomic writes, force-refresh; handoff to parsing layer

**Independent Test**: Second `fetch_filing` for same accession returns `cache_hit=true` and skips network; `--force-refresh` re-downloads

### Implementation for User Story 2

- [x] T024 [US2] Implement `cache_manager.py` with atomic temp-dir + rename writes in `src/ingestion/cache_manager.py`
- [x] T025 [US2] Implement per-artifact and package content hashing; persist hashes in `manifest.json`
- [x] T026 [US2] Integrate cache lookup into `fetch_filing()` with `force_refresh` flag
- [x] T027 [US2] Add `src/parsing/sec_download_adapter.py` to read `CacheEntry` and produce `ParsedDocument` via Docling
- [x] T028 [US2] Extend `src/parsing/docling_pipeline.py` to locate primary instance XML from manifest roles
- [x] T029 [P] [US2] Add contract test ingestion→parsing in `tests/contract/test_ingestion_parsing.py`
- [x] T030 [P] [US2] Add integration test cache hit/miss in `tests/integration/test_cache_roundtrip.py`
- [x] T031 [US2] Wire `graph.cli build` to accept `--ticker` path under `data/parsed/{ticker}/` in `src/graph/cli.py`

**Checkpoint**: Parse + graph build succeeds from `sec_downloads/` without manual `sec-ingest`

---

## Phase 5: User Story 3 - Unified Developer CLI (Priority: P3)

**Goal**: `uv run agent-query ask` and `agent-query test` orchestrate full pipeline

**Independent Test**: `uv run agent-query ask --ticker AAPL --query "..."` prints answer + citations + mlflow_run_id (mock LLM in CI)

### Implementation for User Story 3

- [x] T032 [US3] Implement `src/cli/pipeline.py` with staged orchestration and `timings_ms` per `contracts/agent-query-cli.md`
- [x] T033 [US3] Implement `src/cli/commands/ask.py` with `--ticker`, `--cik`, `--accession`, `--query`, `--form`, `--force-refresh`, `--json`
- [x] T034 [US3] Implement identifier conflict validation (ticker vs CIK mismatch) in `src/cli/commands/ask.py`
- [x] T035 [US3] Integrate `QueryService` from `src/retrieval/service.py` in ask pipeline (no orchestration imports)
- [x] T036 [US3] Implement human-readable and JSON stdout formatters in `src/cli/commands/ask.py`
- [x] T037 [US3] Implement `src/cli/commands/test.py` with structural graph thresholds (`--min-sections`, `--min-chunk-tables`)
- [x] T038 [US3] Wire Typer app in `src/cli/main.py` with `ask` and `test` subcommands
- [x] T039 [US3] Add MLflow parent run metadata (`ticker`, `accession`) in `src/cli/pipeline.py` via `tracing/mlflow_langgraph.py`
- [x] T040 [P] [US3] Add contract test CLI does not import `retrieval.orchestration` in `tests/contract/test_cli_imports.py`
- [x] T041 [P] [US3] Add integration test `agent-query ask` with mocks in `tests/integration/test_agent_query_ask.py`
- [x] T042 [P] [US3] Add integration test `agent-query test` in `tests/integration/test_agent_query_test.py`

**Checkpoint**: End-to-end `agent-query ask` succeeds on mock path; live path validated with SEC_API_KEY + LM Studio

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, observability, and hardening

- [x] T043 [P] Update `README.md` with `agent-query` quickstart and `SEC_API_KEY` setup
- [x] T044 Align `specs/002-live-disclosure-cli/quickstart.md` with implemented CLI flags
- [x] T045 [P] Add structured logging for fetch/cache operations in `src/ingestion/cache_manager.py`
- [x] T046 [P] Add retry/backoff on sec-api 429/5xx in `src/ingestion/sec_client.py`
- [x] T047 Add optional `--check-registry` flag to `agent-query test` reading threshold JSON from `specs/002-live-disclosure-cli/contracts/`
- [x] T048 Run full test suite and fix any layer import regressions

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Setup (P0) → Foundational → US1 (fetch) → US2 (cache + parse adapter) → US3 (CLI) → Polish
```

### User Story Dependencies

```text
US1 (P1) ──► US2 (P2) ──► US3 (P3)
```

US3 requires US2 (parse adapter + cache); US2 requires US1 (fetch + manifest).

### Parallel Opportunities

- **Phase 1**: T004, T005, T006, T008 in parallel
- **Phase 2**: T012, T013, T014 in parallel
- **Phase 3**: T015+T022 parallel after T010; T023 after T018
- **Phase 4**: T029, T030 parallel after T027
- **Phase 5**: T040, T041, T042 parallel after T038
- **Phase 6**: T043, T045, T046 parallel

---

## Parallel Example: User Story 1

```bash
# After T014:
# T015: src/ingestion/sec_client.py (resolution)
# T022: tests/ingestion/test_sec_client.py

# After T018:
# T023: tests/ingestion/test_xbrl_downloader.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2
2. Complete Phase 3 (US1): live fetch to `sec_downloads/`
3. **STOP and VALIDATE**: manifest + files on disk for AAPL 10-K
4. Demo before cache optimization or CLI

### Incremental Delivery

1. Setup + Foundational
2. US1 → manual fetch API
3. US2 → cache + parsing adapter + graph from live data
4. US3 → `agent-query ask` / `test`
5. Polish → retries, docs, registry checks

### Suggested MVP Scope

**User Story 1** (T001–T023): Live XBRL fetch and manifest validation only.

---

## Task Summary

| Phase | Task IDs | Count |
|-------|----------|-------|
| Setup | T001–T008 | 8 |
| Foundational | T009–T014 | 6 |
| US1 (P1) | T015–T023 | 9 |
| US2 (P2) | T024–T031 | 8 |
| US3 (P3) | T032–T042 | 11 |
| Polish | T043–T048 | 6 |
| **Total** | **T001–T048** | **48** |

**Parallel opportunities**: 16 tasks marked `[P]`  
**Independent test criteria**: Documented per user story phase header
