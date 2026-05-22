# Implementation Plan: Ask Console Trajectory Trace

**Branch**: `007-ask-console-trace` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)

**Input**: Beautified **stderr** console trajectory for `agent-query ask` — streaming per-stage trace, optional JSONL, registry-coupled to LangGraph stages; stdout remains answer/`--json` only. Builds on **005** (intent router, trajectory) and **002** ask CLI.

## Summary

Introduce a **`src/tracing/console_trace/`** package that (1) collects **`TraceEvent`** records in **`AgentState.trace_events`**, (2) wraps each LangGraph node to emit start/end + stage payloads without duplicating router logic, (3) routes all ask-path LLM calls through **`traced_llm_invoke`**, (4) streams **Rich** panels to **stderr** per stage via **`ConsoleTraceReporter`**, (5) optionally emits **JSONL** on stderr with **`--trace-json`**, and (6) enforces **`ASK_TRACE_REGISTRY` ↔ graph node** bijection in CI contract tests so routing/extraction changes cannot merge without trace updates.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Primary dependencies** (existing): `langgraph`, `langchain-openai`, `pydantic`, `typer`, `mlflow`, `rich` (add to `pyproject.toml`)

**Reuse (unchanged boundaries)**:

| Module | Role |
|--------|------|
| `retrieval/orchestration/graph.py` | Wrap nodes with `_traced_node`; stage list authority |
| `retrieval/orchestration/nodes/*` | Add `build_*_trace_payload(state)` helpers only |
| `retrieval/orchestration/llm.py` | Delegate invoke to `traced_llm_invoke` when trace enabled |
| `retrieval/service.py` | Build `TraceRunConfig`, attach reporter, pass to graph invoke |
| `cli/commands/ask.py` | `--trace`, `--trace-json`; resolve level precedence |
| `tracing/mlflow_langgraph.py` | Unchanged MLflow trajectory (complementary) |
| `models/query.py` | Read-only for renderers (`IntentRouterTrace`, etc.) |

**New modules**:

| Module | Role |
|--------|------|
| `tracing/console_trace/models.py` | `TraceEvent`, `LlmIoRecord`, `TraceRunConfig`, enums |
| `tracing/console_trace/emitter.py` | `trace_emit`, `trace_stage_payload` |
| `tracing/console_trace/registry.py` | `ASK_TRACE_REGISTRY`, renderers |
| `tracing/console_trace/reporter.py` | `ConsoleTraceReporter` (Rich → stderr) |
| `tracing/console_trace/llm.py` | `traced_llm_invoke` |
| `tracing/console_trace/config.py` | Load `configs/trace.yaml` |
| `retrieval/orchestration/trace_payloads.py` | Per-stage payload builders (no formatting) |
| `configs/trace.yaml` | Preview char limits, panel toggles |

**Testing**: `pytest` — registry contract, schema drift, formatter unit tests (fixture state), integration stderr/stdout separation, golden normalized snapshots (numeric + qualitative mock).

**Performance goals**:

- `--trace quiet`: < 5% wall-clock overhead vs baseline (SC-005)
- `--trace normal`: streaming flush < 50 ms p90 per stage (formatting only)

**Constraints**:

- Observability only — no change to routing ranks or answers (FR-002)
- No consolidated CoT paragraph (FR-004b)
- stderr trace / stdout answer split (clarification)
- Per-stage summaries derived from state, not LLM narration

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Trace displays existing evidence/plan fields; no new claims in console |
| **II. Structural Semantics Preservation** | PASS | No parsing/graph changes |
| **III. Traceability** | PASS | Console projects same fields as `TrajectoryRecord` + MLflow; enhances operator audit |
| **IV. Separation of Concerns** | PASS | `tracing/console_trace/` separate from nodes; nodes only emit events |
| **V. Code Health & Environment Stability** | PASS | Pydantic events; registry contract in CI; `uv.lock` + `rich` |
| **VI. Rigorous Agent Evaluation** | PASS | Eval still uses MLflow trajectory; console not required for benchmarks |

**Post-design re-check**: Contracts in [contracts/](./contracts/) define stderr/stdout, registry, JSONL schema; no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-ask-console-trace/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── ask-trace-registry.md
│   ├── ask-cli-trace-flags.md
│   └── trace-event-schema.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source (repository root)

```text
src/
├── tracing/
│   └── console_trace/          # NEW package
│       ├── models.py
│       ├── emitter.py
│       ├── registry.py
│       ├── reporter.py
│       ├── llm.py
│       └── config.py
├── retrieval/
│   ├── orchestration/
│   │   ├── graph.py            # _traced_node wrappers
│   │   ├── state.py            # + trace_events, trace_config
│   │   └── trace_payloads.py   # NEW stage payload builders
│   └── service.py              # wire reporter + config
├── cli/commands/ask.py         # --trace, --trace-json
configs/trace.yaml              # NEW

tests/
├── contract/
│   ├── test_ask_trace_registry.py
│   └── test_ask_trace_schema.py
├── unit/
│   └── test_console_trace_*.py
├── integration/
│   └── test_ask_trace_streams.py
└── fixtures/console_trace/     # golden stderr (normalized)
```

**Structure Decision**: Single Python package under `src/tracing/console_trace/` keeps observability out of router business logic while remaining in the agentic retrieval call path via thin wrappers.

## Implementation Phases (for `/speckit-tasks`)

### Phase A — Models & config (P1)

- `TraceEvent`, `TraceRunConfig`, enums
- `configs/trace.yaml` + loader
- Extend `AgentState` with `trace_events`, `trace_config`
- CLI flag parsing + precedence (`ask.py`)

### Phase B — Registry & contracts (P1)

- `ASK_TRACE_REGISTRY` with five stage renderers
- `tests/contract/test_ask_trace_registry.py` (graph ↔ registry)
- `tests/contract/test_ask_trace_schema.py` (field drift)

### Phase C — Instrumentation (P1)

- `trace_payloads.py` for macro/intent/meso/micro/synthesize
- `_traced_node` in `graph.py`
- `traced_llm_invoke` in intent_router, macro_router (LLM path), synthesis
- `ConsoleTraceReporter.flush_stage` streaming to stderr

### Phase D — JSONL & integration (P2)

- `--trace-json` JSONL on stderr
- `tests/integration/test_ask_trace_streams.py` (stdout vs stderr)
- Golden snapshots (mock LLM, qualitative + numeric queries)

### Phase E — Polish (P3)

- README section for `--trace`, `AGENT_QUERY_TRACE`
- `.github/workflows/ci.yml` — ensure contract tests run on PR
- Context overflow retry visible in synthesize payload

## Complexity Tracking

No constitution violations requiring justification.
