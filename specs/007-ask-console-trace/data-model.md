# Data Model: Ask Console Trajectory Trace (007)

**Feature**: 007 | **Date**: 2026-05-22

## Enumerations (`models/enums.py` or `tracing/console_trace/enums.py`)

| Enum | Values | Use |
|------|--------|-----|
| `TraceLevel` | `quiet`, `normal`, `verbose` | CLI `--trace` / `AGENT_QUERY_TRACE` |
| `TraceEventType` | `stage_start`, `stage_end`, `llm_io`, `routing_decision`, `evidence_snapshot` | Event discriminator |

## `TraceEvent` (NEW — `models/trace.py` or `tracing/console_trace/models.py`)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `stage_id` | `str` | yes | Must match LangGraph node name |
| `event_type` | `TraceEventType` | yes | |
| `timestamp` | `datetime` | yes | UTC |
| `duration_ms` | `int \| None` | no | Set on `stage_end`, `llm_io` |
| `decision_summary` | `str` | no | One line; no invented CoT |
| `payload` | `dict` | no | Stage-specific structured fields |
| `llm_io` | `LlmIoRecord \| None` | no | When `event_type=llm_io` |

## `LlmIoRecord`

| Field | Type | Notes |
|-------|------|-------|
| `model_id` | `str` | |
| `temperature` | `float \| None` | |
| `max_tokens` | `int \| None` | |
| `messages_preview` | `list[dict]` | `{role, content}` truncated |
| `response_preview` | `str` | truncated |
| `latency_ms` | `int` | |
| `error` | `str \| None` | |

## `TraceStageRegistration` (registry entry)

| Field | Type | Notes |
|-------|------|-------|
| `stage_id` | `str` | |
| `title` | `str` | Console header |
| `order` | `int` | Execution order |
| `schema_version` | `int` | Bump on payload shape change |
| `state_field_map` | `list[str]` | AgentState keys rendered (e.g. `intent_trace`) |

## Extended: `AgentState`

| Field | Type | Merge | Notes |
|-------|------|-------|-------|
| `trace_events` | `Annotated[list[TraceEvent], _merge_events]` | append | All stages + llm_io |
| `trace_config` | `TraceRunConfig \| None` | replace | Resolved level + limits for run |

## `TraceRunConfig`

| Field | Type | Notes |
|-------|------|-------|
| `level` | `TraceLevel` | |
| `emit_jsonl` | `bool` | `--trace-json` |
| `prompt_preview_chars` | `int` | from `configs/trace.yaml` |
| `excerpt_preview_chars` | `int` | |
| `use_color` | `bool` | TTY + not NO_COLOR |

## Reuse (read-only for renderers)

| Model | Stage(s) | Fields displayed |
|-------|----------|------------------|
| `IntentRouterTrace` | `intent_router` | `query_intent`, `intent_source`, `source_bias_applied`, `router_fallback_reason`, `router_model_id`, `router_latency_ms` |
| `MacroPlan` | `macro_router` | `intent_summary`, `temporal_scope`, `rationale` |
| `list[FilingRef]` | `macro_router` | accessions, form, period labels |
| `list[SectionCandidate]` | `meso_router` | `section_node_id`, `score`, `path` |
| `list[EvidenceChunk]` | `micro_extractor` | previews, `source_type`, counts before/after |
| `list[GraphVisit]` | `meso_router`, `micro_extractor` | `node_id`, `stage`, `path_edge_types` |
| Context budget dict | `synthesize` | `context_tokens`, chunk limits (from `load_context_budget`) |

## Registry invariant

```text
set(build_agent_graph().get_graph().nodes.keys()) - {"__start__", "__end__"}
  ==
set(ASK_TRACE_REGISTRY.keys())
```

Current expected keys: `macro_router`, `intent_router`, `meso_router`, `micro_extractor`, `synthesize`.

## JSONL stderr contract

Each line: `TraceEvent.model_dump_json()` (one object per line). Emitted on stage flush when `emit_jsonl=true`.
