# Contract: Ask Trace Registry & Evolution

**Feature**: 007-ask-console-trace  
**Authority**: Ask execution graph stage list (must match registry keys)

## Invariant

Every stage in the ask execution graph has exactly one registry entry with the same identifier. No registry entry exists without a corresponding graph stage.

## Trace event types

| Event type | Purpose |
|------------|---------|
| `stage_start` | Stage began |
| `stage_end` | Stage finished with duration and decision summary |
| `llm_io` | Language-model request and response preview |
| `routing_decision` | Structured routing outcome for macro, intent, meso, or micro |
| `evidence_snapshot` | Counts and top evidence previews after extraction |

New event types require registry and contract test updates before use.

## Change protocol

1. Change routing or extraction logic.
2. Update trace event payload for that stage in the same change.
3. Register or bump schema version in the ask trace registry.
4. Update registry contract tests and golden console snapshots when output changes.

## Forbidden

- Duplicating ranking or classification logic inside console formatters.
- Adding ask-graph stages without registry entries.
- Embedding trace printing inside router or extractor business modules.
