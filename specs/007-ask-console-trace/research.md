# Research: Ask Console Trajectory Trace (007)

**Feature**: 007 | **Date**: 2026-05-22

## R1: Console formatting library

**Decision**: Use **Rich** (`rich.console.Console`) writing to **stderr**; plain-text fallback when `stderr.isatty()` is false or `NO_COLOR` is set.

**Rationale**: Spec requires sectioned, colorized layout (panels, headers). Rich is already common in Python CLIs, supports non-TTY fallback, and keeps formatters out of retrieval nodes.

**Alternatives considered**:
- **Typer only** — insufficient structure for multi-stage panels.
- **structlog** — optimized for logs, not human stage narrative.
- **Custom ANSI** — higher maintenance than Rich.

## R2: Trace emission architecture (registry coupling)

**Decision**: **`TraceEvent` Pydantic models** appended to `AgentState.trace_events` via `trace_emit()` helper; **`ASK_TRACE_REGISTRY`** maps graph node names → renderer; contract test compares `build_agent_graph().get_graph().nodes` to registry keys.

**Rationale**: Satisfies FR-014–019: new graph nodes fail CI without registry entry; formatters never duplicate router logic.

**Alternatives considered**:
- **Print from each node** — drifts from graph changes (rejected).
- **Post-hoc MLflow-only replay** — misses streaming requirement.
- **LangGraph callbacks only** — harder to attach stage-specific payloads (macro vs micro).

## R3: Streaming render timing

**Decision**: **`ConsoleTraceReporter.flush_stage(stage_id)`** called at end of each node wrapper (or inside node before return) when trace level is `normal`/`verbose`; JSONL line emitted per event batch on stderr when `--trace-json`.

**Rationale**: Clarification session: streaming per stage on stderr; answer on stdout.

**Alternatives considered**:
- **Batch at end** — rejected by clarification.
- **Separate thread** — unnecessary complexity for linear graph.

## R4: LLM I/O capture

**Decision**: **`traced_llm_invoke(stage_id, llm, messages, ...)`** in `src/tracing/console_trace/llm.py` wraps `ChatOpenAI.invoke`, records `llm_io` events with truncated message bodies from `configs/trace.yaml`.

**Rationale**: Single interception point for intent_router, macro_router (when used), synthesis; satisfies FR-008 without patching LangChain globally.

**Alternatives considered**:
- **LangChain callbacks** — harder to tie to stage_id and truncation policy.
- **Monkeypatch ChatOpenAI** — fragile across upgrades.

## R5: Default trace level resolution

**Decision**: Resolve in CLI: `explicit --trace` > `AGENT_QUERY_TRACE` env > TTY heuristic (`normal` if stderr TTY else `quiet`).

**Rationale**: Matches clarification C; CI can set `AGENT_QUERY_TRACE=normal` without flags.

## R6: Golden snapshot tests

**Decision**: Store **normalized plain-text** snapshots (strip ANSI, stable timestamps) under `tests/fixtures/console_trace/`; optional separate Rich snapshot behind env flag.

**Rationale**: FR-018 requires golden updates on visible change; ANSI in git is brittle.

**Alternatives considered**:
- **Full ANSI snapshots** — rejected for CI stability.

## R7: Graph node instrumentation pattern

**Decision**: Thin **wrappers in `graph.py`** (`_traced_node(fn, stage_id)`) that: emit `stage_start`, run node, emit `stage_end` + call `reporter.flush_stage`, return state update.

**Rationale**: Avoid editing every node file for start/end; centralizes stage boundaries; wrappers registered in registry by `stage_id`.

**Alternatives considered**:
- **Duplicate code in each node** — error-prone for FR-014.
