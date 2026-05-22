# Contract: Ask Trace Registry & Evolution

**Feature**: 007-ask-console-trace  
**Authority**: `src/retrieval/orchestration/graph.py` → `build_agent_graph()` node names

## Invariant

```text
graph_nodes - {__start__, __end__} == registry_keys
```

## Registered stages (v1)

| `stage_id` | `order` | `state_field_map` | Primary events |
|------------|---------|-------------------|----------------|
| `macro_router` | 1 | `macro_plan`, `filing_set` | `routing_decision`, `llm_io` (optional) |
| `intent_router` | 2 | `intent_trace` | `routing_decision`, `llm_io` |
| `meso_router` | 3 | `section_candidates`, `graph_traversal` | `routing_decision` |
| `micro_extractor` | 4 | `evidence_chunks`, `graph_traversal` | `evidence_snapshot`, `routing_decision` |
| `synthesize` | 5 | `answer`, `status` | `stage_end`, `llm_io` |

## Trace event types

| `event_type` | Emitted by |
|--------------|------------|
| `stage_start` | Node wrapper |
| `stage_end` | Node wrapper |
| `llm_io` | `traced_llm_invoke` |
| `routing_decision` | Stage payload builder |
| `evidence_snapshot` | `micro_extractor` |

New `event_type` values require registry + `test_ask_trace_registry.py` update.

## Change protocol

1. Change routing/extraction logic in `orchestration/nodes/`.
2. Update stage `build_trace_payload(state)` in same PR.
3. Register or bump `schema_version` in `ASK_TRACE_REGISTRY`.
4. Run `tests/contract/test_ask_trace_registry.py` and update golden snapshots if stderr text changes.

## Forbidden

- Ranking/filtering/intent logic inside formatters.
- `typer.echo` trace content inside node business logic.
- Graph nodes without registry entries.
