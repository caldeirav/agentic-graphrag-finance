---
description: "Task list for ask console trajectory trace (007)"
---

# Tasks: Ask Console Trajectory Trace

**Input**: Design documents from `specs/007-ask-console-trace/`

**Prerequisites**: `005-html-narrative-supplement` merged on branch; plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit, contract, and integration tests per spec success criteria (registry gate, stderr/stdout separation, formatter fixtures).

**Organization**: Tasks grouped by user story (US4 foundational registry → US1 → US2 → US3). Builds on existing LangGraph ask pipeline — **observability only**, no routing behavior changes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps)
- **[USn]**: User story label

## Path Conventions

- New: `src/tracing/console_trace/`, `configs/trace.yaml`, `src/retrieval/orchestration/trace_payloads.py`
- Extend: `src/retrieval/orchestration/graph.py`, `state.py`, `nodes/*.py`, `service.py`, `synthesis.py`, `src/cli/commands/ask.py`, `pyproject.toml`, `.github/workflows/ci.yml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency, trace config, operator docs stub

- [x] T001 [P] Add `rich` to `pyproject.toml` and refresh `uv.lock` via `uv lock` per `research.md` R1
- [x] T002 [P] Add `configs/trace.yaml` with `prompt_preview_chars`, `excerpt_preview_chars`, `panel_enabled` per `data-model.md`
- [x] T003 [P] Implement `load_trace_config()` in `src/tracing/console_trace/config.py` reading `configs/trace.yaml` and env overrides

**Checkpoint**: `uv run python -c "from tracing.console_trace.config import load_trace_config; load_trace_config()"` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Trace models, registry skeleton, contract gates (US4 core) — MUST complete before user story phases

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T004 [P] Add `TraceLevel`, `TraceEventType` to `src/tracing/console_trace/models.py` (or `src/models/enums.py` if re-exported) per `data-model.md`
- [x] T005 [P] Implement `TraceEvent`, `LlmIoRecord`, `TraceRunConfig` Pydantic models in `src/tracing/console_trace/models.py`
- [x] T006 Extend `AgentState` in `src/retrieval/orchestration/state.py` with `trace_events` (append reducer) and `trace_config` per `data-model.md`
- [x] T007 Implement `trace_emit()` and `trace_stage_start`/`trace_stage_end` helpers in `src/tracing/console_trace/emitter.py`
- [x] T008 Scaffold `ASK_TRACE_REGISTRY` with five stage entries (`macro_router`, `intent_router`, `meso_router`, `micro_extractor`, `synthesize`) in `src/tracing/console_trace/registry.py` per `contracts/ask-trace-registry.md`
- [x] T009 [P] Add contract test `tests/contract/test_ask_trace_registry.py` asserting graph node keys == registry keys (fails on missing stage) per FR-006
- [x] T010 [P] Add contract test `tests/contract/test_ask_trace_schema.py` snapshot of trace-relevant fields on `IntentRouterTrace`, `MacroPlan`, `EvidenceChunk` per FR-016
- [x] T011 [P] Add unit test `tests/unit/test_trace_emitter.py` for append-only `trace_events` merge and event serialization

**Checkpoint**: `uv run pytest tests/contract/test_ask_trace_registry.py tests/unit/test_trace_emitter.py -q` passes

---

## Phase 3: User Story 1 - Stage-by-Stage Console Trace (Priority: P1) 🎯 MVP

**Goal**: `--trace normal` streams beautified per-stage sections on stderr; `--trace quiet` preserves minimal stdout; answer/json on stdout only

**Independent Test**: `USE_MOCK_LLM=1 uv run agent-query ask --ticker AAPL --query "..." --trace normal` shows five ordered stage sections on stderr before answer on stdout

### Tests for User Story 1

- [x] T012 [P] [US1] Add unit test `tests/unit/test_console_trace_reporter.py` rendering fixture `trace_events` to normalized plain text (no ANSI) per `research.md` R6
- [x] T013 [US1] Add integration test `tests/integration/test_ask_trace_streams.py` asserting stdout has no trace keys under `--json --trace quiet` and stderr receives stage headers under `--trace normal` per SC-006

### Implementation for User Story 1

- [x] T014 [US1] Implement `ConsoleTraceReporter` with Rich panels writing to stderr and plain fallback in `src/tracing/console_trace/reporter.py` per FR-003
- [x] T015 [US1] Implement `_traced_node(fn, stage_id)` wrapper emitting start/end + calling `reporter.flush_stage` in `src/retrieval/orchestration/graph.py`
- [x] T016 [US1] Wrap all five graph nodes with `_traced_node` in `src/retrieval/orchestration/graph.py` preserving existing edges
- [x] T017 [P] [US1] Add stub `build_*_trace_payload` returning minimal `decision_summary` in `src/retrieval/orchestration/trace_payloads.py` (one function per stage)
- [x] T018 [US1] Wire payload builders into `_traced_node` via registry `state_field_map` in `src/tracing/console_trace/registry.py`
- [x] T019 [US1] Implement `resolve_trace_level()` (CLI > `AGENT_QUERY_TRACE` > TTY) in `src/cli/commands/ask.py` per `contracts/ask-cli-trace-flags.md`
- [x] T020 [US1] Add `--trace {quiet,normal,verbose}` Typer option to `ask` in `src/cli/commands/ask.py`
- [x] T021 [US1] Build `TraceRunConfig` in `src/retrieval/service.py` and pass into graph `initial` state; attach `ConsoleTraceReporter` for run duration
- [x] T022 [US1] Ensure `ask` prints answer + status footer on stdout only; move any trace echo out of stdout paths in `src/cli/commands/ask.py`
- [x] T023 [US1] Emit final stderr summary footer (duration, status, citations) from `ConsoleTraceReporter` after graph completes in `src/retrieval/service.py`

**Checkpoint**: US1 quickstart steps 1–2 pass; SC-001 mock run shows five stages on stderr

---

## Phase 4: User Story 4 - Trace Stays in Sync When Graph Evolves (Priority: P1)

**Goal**: Registry contract fails CI when graph stages or trace payloads drift; change protocol documented

**Independent Test**: Temporarily add dummy node to graph without registry — `test_ask_trace_registry` fails naming missing `stage_id`

### Implementation for User Story 4

- [x] T024 [US4] Register per-stage `schema_version` and renderer callables in `src/tracing/console_trace/registry.py` (no ranking logic in renderers) per FR-007
- [x] T025 [US4] Add `get_ask_graph_stage_ids()` helper imported by contract test from `src/retrieval/orchestration/graph.py`
- [x] T026 [US4] Extend `test_ask_trace_registry.py` to validate registered `event_type` values and `state_field_map` keys exist on `AgentState`
- [x] T027 [US4] Add CI step or path filter in `.github/workflows/ci.yml` running `tests/contract/test_ask_trace_registry.py` on PRs touching `src/retrieval/orchestration/` per FR-019
- [x] T028 [P] [US4] Document registry change protocol in `specs/007-ask-console-trace/contracts/ask-trace-registry.md` cross-link from `README.md` (trace section)

**Checkpoint**: SC-003 — deliberate unregistered node fails contract in <1s

---

## Phase 5: User Story 2 - LLM Routing & Full LLM I/O Visibility (Priority: P2)

**Goal**: Intent/macro/synthesis LLM calls traced via `traced_llm_invoke`; fallback and verbose prompt previews visible

**Independent Test**: Mock LLM run shows `intent_source=keyword_fallback` on stderr; verbose shows truncated synthesis prompts

### Tests for User Story 2

- [x] T029 [P] [US2] Add unit test `tests/unit/test_traced_llm_invoke.py` asserting `llm_io` events with truncated messages in `src/tracing/console_trace/llm.py`
- [x] T030 [US2] Extend `tests/unit/test_console_trace_reporter.py` for intent_router panel with fallback reason vs LLM source

### Implementation for User Story 2

- [x] T031 [US2] Implement `traced_llm_invoke(stage_id, llm, messages, ...)` in `src/tracing/console_trace/llm.py` per `research.md` R4
- [x] T032 [US2] Replace direct `llm.invoke` with `traced_llm_invoke` in `src/retrieval/orchestration/nodes/intent_router.py`
- [x] T033 [US2] Replace direct `llm.invoke` with `traced_llm_invoke` in `src/retrieval/orchestration/nodes/macro_router.py` (LLM path only)
- [x] T034 [US2] Replace direct `llm.invoke` with `traced_llm_invoke` in `src/retrieval/synthesis.py`
- [x] T035 [US2] Implement `build_intent_router_trace_payload` mirroring `IntentRouterTrace` fields in `src/retrieval/orchestration/trace_payloads.py`
- [x] T036 [US2] Implement `build_macro_router_trace_payload` with `pre_bound`, `llm_skipped`, filing list in `src/retrieval/orchestration/trace_payloads.py`
- [x] T037 [US2] Register intent/macro renderers showing `query_intent`, `intent_source`, `router_fallback_reason`, `llm_io` previews in `src/tracing/console_trace/registry.py`
- [x] T038 [US2] Gate full prompt/response body display behind `--trace verbose` in `src/tracing/console_trace/reporter.py`

**Checkpoint**: US2 quickstart steps 5–6; SC-004 reviewer can read intent from stderr trace

---

## Phase 6: User Story 3 - Extraction & Retrieval Decision Trail (Priority: P3)

**Goal**: Meso/micro/synthesize panels show section candidates, evidence counts, traversal, context budget

**Independent Test**: Qualitative AAPL ask stderr shows HTML bias and evidence before/after counts in micro_extractor section

### Tests for User Story 3

- [x] T039 [P] [US3] Add unit test `tests/unit/test_trace_payloads_micro.py` for `evidence_snapshot` payload shape per `contracts/trace-event-schema.md`
- [x] T040 [US3] Add golden fixture `tests/fixtures/console_trace/qualitative_mock.txt` (normalized stderr) updated when payload changes per FR-018

### Implementation for User Story 3

- [x] T041 [US3] Implement `build_meso_router_trace_payload` with `section_candidates` top-N in `src/retrieval/orchestration/trace_payloads.py`
- [x] T042 [US3] Implement `build_micro_extractor_trace_payload` with `count_before`, `count_after`, `source_bias`, `top_chunks` previews in `src/retrieval/orchestration/trace_payloads.py`
- [x] T043 [US3] Implement `build_synthesize_trace_payload` with `evidence_in_prompt`, context budget from `load_context_budget()`, sufficiency in `src/retrieval/orchestration/trace_payloads.py`
- [x] T044 [US3] Register meso/micro/synthesize renderers displaying `graph_traversal` visits in `src/tracing/console_trace/registry.py`
- [x] T045 [US3] Surface synthesis context-overflow retry in `build_synthesize_trace_payload` when tighter budget applied in `src/retrieval/synthesis.py`
- [x] T046 [P] [US3] Add golden fixture `tests/fixtures/console_trace/numeric_mock.txt` for numeric pilot query stderr snapshot

**Checkpoint**: US3 quickstart qualitative/numeric scenarios; meso/micro sections populated on live corpus

---

## Phase 7: JSONL & Cross-Cutting (supports US1–US3)

**Purpose**: `--trace-json`, JSONL stderr, polish

- [x] T047 [P] Emit JSONL `TraceEvent.model_dump_json()` lines on stderr per stage flush when `--trace-json` in `src/tracing/console_trace/reporter.py` per FR-011
- [x] T048 Add `--trace-json` flag to `src/cli/commands/ask.py` and set `TraceRunConfig.emit_jsonl` in `src/retrieval/service.py`
- [x] T049 Extend `tests/integration/test_ask_trace_streams.py` for `--trace-json` JSONL line count >= stage count per SC-007
- [x] T050 [P] Document `--trace`, `AGENT_QUERY_TRACE`, stderr/stdout split in `README.md` linking `specs/007-ask-console-trace/quickstart.md`
- [x] T051 Run full quickstart validation and mark completed items in `specs/007-ask-console-trace/checklists/requirements.md`

**Checkpoint**: quickstart.md steps 1–8 pass on fixture + optional live LM Studio

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — **MVP**
- **US4 (Phase 4)**: Depends on Phase 2; can overlap late US1 (T024–T028 after T008)
- **US2 (Phase 5)**: Depends on US1 reporter + graph wrappers (T014–T016)
- **US3 (Phase 6)**: Depends on US1 payloads stub (T017); best after US2 intent payloads (T035)
- **JSONL (Phase 7)**: Depends on US1 reporter flush path

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 (P1) | Foundational | MVP — streaming stderr trace |
| US4 (P1) | Foundational | Registry CI gate; completes during/after US1 |
| US2 (P2) | US1 wrappers + reporter | LLM I/O |
| US3 (P3) | US1 + US2 intent payloads | Retrieval trail detail |

### Parallel Opportunities

- Phase 1: T001–T003 all [P]
- Phase 2: T004–T005, T009–T011 [P] after T007
- US1: T012 parallel with T014; T017 parallel with T014
- US2: T029 parallel with T031
- US3: T039 parallel with T041
- Phase 7: T047 parallel with T050

---

## Parallel Example: Foundational

```bash
# Models + contracts in parallel:
T004 TraceEvent enums in src/tracing/console_trace/models.py
T005 Pydantic models in src/tracing/console_trace/models.py
T009 tests/contract/test_ask_trace_registry.py
T010 tests/contract/test_ask_trace_schema.py
```

---

## Parallel Example: User Story 1

```bash
T012 tests/unit/test_console_trace_reporter.py
T014 src/tracing/console_trace/reporter.py
T017 src/retrieval/orchestration/trace_payloads.py  # stubs
```

---

## Implementation Strategy

### MVP First (User Story 1 + Foundational)

1. Phase 1 Setup
2. Phase 2 Foundational (registry contract)
3. Phase 3 US1 — streaming stderr trace, `--trace quiet|normal`
4. **STOP and VALIDATE** quickstart §1–2 with `USE_MOCK_LLM=1`

### Incremental Delivery

1. Foundational + US1 → MVP operator trace
2. US4 → CI gate hardened
3. US2 → LLM I/O visibility
4. US3 → retrieval/evidence detail
5. Phase 7 → JSONL + README

### Suggested MVP scope

**Phases 1–3 only** (T001–T023): delivers FR-001–004a, FR-003, stderr streaming, quiet mode — sufficient for daily debugging without JSONL or verbose LLM bodies.

---

## Notes

- Do not add ranking/filtering logic to `registry.py` renderers (FR-007)
- Do not `typer.echo` trace content inside `nodes/*.py` business logic (FR-004)
- Bump registry `schema_version` when payload shapes change (FR-016)
- Commit after each phase checkpoint; run `pytest tests/contract/test_ask_trace_registry.py` before merging orchestration changes
