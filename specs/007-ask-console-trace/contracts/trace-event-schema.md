# Contract: TraceEvent JSONL Schema

**Feature**: 007 | **Version**: 1

## Line format

One JSON object per line on **stderr** when `--trace-json` is set. UTF-8. No wrapping array.

## Required fields (all events)

| Field | Type |
|-------|------|
| `stage_id` | string |
| `event_type` | string (enum value) |
| `timestamp` | ISO-8601 string |

## `stage_end` payload

| Field | Type | Required |
|-------|------|----------|
| `duration_ms` | integer | yes |
| `decision_summary` | string | yes |
| `payload` | object | optional stage-specific |

### Stage-specific `payload` keys

**macro_router**: `pre_bound`, `filing_accessions`, `comparison_mode`, `llm_skipped`

**intent_router**: `query_intent`, `intent_source`, `source_bias_applied`, `router_fallback_reason`

**meso_router**: `candidate_count`, `top_section_ids`

**micro_extractor**: `count_before`, `count_after`, `source_bias`, `top_chunks` (array of `{chunk_node_id, source_type, section_id, excerpt_preview}`)

**synthesize**: `evidence_in_prompt`, `context_tokens`, `sufficiency`, `retry_tighter_budget`

## `llm_io` event

Uses `llm_io` object (see data-model.md) instead of generic `payload`.

## Stability

- Contract tests snapshot canonical field names per `schema_version` in registry.
- Adding required payload keys requires registry `schema_version` bump.
