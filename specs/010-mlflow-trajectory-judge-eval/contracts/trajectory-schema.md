# Agent Trajectory Schema Contract (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Artifact**: `agent_trajectory.json` (MLflow)  
**Schema version**: `1.0.0` (initial)

## Purpose

Versioned derived snapshot for validator, judge, and CI. **Secondary** to MLflow Trace for human exploration; **primary** for deterministic evaluation pipelines (FR-001a).

## Top-level shape

```json
{
  "schema_version": "1.0.0",
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "query_text": "...",
  "issuer_id": "AAPL",
  "snapshot_id": "...",
  "mlflow_run_id": "...",
  "mlflow_trace_id": "optional-trace-id",
  "status": "success",
  "synthesis_path": "live_llm",
  "plan": { },
  "document_route": [ ],
  "graph_traversal": [ ],
  "evidence": [ ],
  "stage_timings_ms": { "macro": 120, "synthesis": 800 },
  "macro_binding": { },
  "navigation_trace": { },
  "intent_router": { }
}
```

## plan (FR-002)

```json
{
  "intent_summary": "YoY net sales comparison",
  "steps_considered": [
    { "stage": "macro", "description": "YoY 10-K pair", "selected": true }
  ],
  "chosen_path_rationale": "...",
  "rejected_alternatives": []
}
```

On macro failure, `intent_summary` and `chosen_path_rationale` MUST still describe the attempted binding; downstream sections use `absent_reason`.

## document_route (FR-003)

```json
{
  "accession": "0000320193-24-000123",
  "form_type": "10-K",
  "period_end": "2024-09-28",
  "fiscal_period_label": "FY2024"
}
```

## graph_traversal (FR-004)

Each hop:

```json
{
  "hop_index": 0,
  "stage": "meso",
  "node_id": "0000320193-24-000123::section:mda",
  "node_type": "section",
  "edge_id": "e-optional",
  "edge_type": "contains",
  "accession_prefix": "0000320193-24-000123"
}
```

**Rules**:
- `edge_type` REQUIRED
- `edge_id` REQUIRED when graph edge has stable id
- Structural containment MAY omit `edge_id` if catalog allows (009 edge catalog)
- `stage` ∈ { `macro`, `intent`, `meso`, `micro`, `audit` }

## evidence (FR-005)

```json
{
  "chunk_node_id": "...",
  "content_hash": "sha256:...",
  "citation_label": "10-K FY2024 — Item 7",
  "source_type": "numeric",
  "accession": "0000320193-24-000123",
  "section_id": "...",
  "in_prompt": true
}
```

MUST list all chunks shortlisted for synthesis, not only `in_prompt: true`.

## synthesis_path

| Value | Meaning |
|-------|---------|
| `live_llm` | LM Studio / remote LLM produced answer |
| `deterministic_fallback` | YoY or numeric fallback |
| `template` | Evidence-list template |

## Relationship to legacy artifacts

| Legacy file | Mapping |
|-------------|---------|
| `trajectory.json` | Deprecated after migration; snapshot supersedes |
| `macro_binding.json` | Copied to `macro_binding` field |
| `navigation_trace.json` | Copied to `navigation_trace` |
| `intent_router.json` | Copied to `intent_router` |

## Contract tests

- `tests/contract/test_trajectory_schema.py` — golden complete snapshot validates against Pydantic model
- `tests/contract/test_trajectory_artifact.py` — ask run logs `agent_trajectory.json` with `schema_version`
