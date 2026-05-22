# Contract: Intent Router Trace (Observability)

**Feature**: 005-html-narrative-supplement | **Spec**: FR-013–016, SC-006–007

## Lifecycle

```text
ask entry → macro_router (filings)
         → intent_router (IntentRouterTrace)  ← MUST complete before micro_extractor
         → meso_router
         → micro_extractor (reads intent_trace.source_bias_applied)
         → synthesize
         → build_trajectory_from_state → log_trajectory + MLflow
```

## Canonical fields

| Field | Type | Always | Notes |
|-------|------|--------|-------|
| `query_intent` | `numeric \| qualitative \| hybrid` | yes | Canonical intent; macro must not overwrite |
| `intent_source` | `llm \| keyword_fallback` | yes | |
| `source_bias_applied` | `xbrl_primary \| html_primary \| blended` | yes | Derived from intent |
| `router_fallback_reason` | enum string | when fallback | Non-empty |
| `router_model_id` | string | when `llm` | e.g. LM Studio model name |
| `router_raw_label` | string | optional | LLM path |
| `router_latency_ms` | int | optional | |

## LangGraph node contract

```python
# src/retrieval/orchestration/nodes/intent_router.py

def intent_router(state: AgentState) -> dict:
    """Returns {"intent_trace": IntentRouterTrace, "graph_traversal": [...]}"""
```

## Trajectory embedding

```python
class TrajectoryRecord(BaseModel):
    plan: MacroPlan | None = None
    intent_router: IntentRouterTrace | None = None  # NEW
    document_route: list[FilingRef] = ...
    graph_traversal: list[GraphVisit] = ...
    evidence: list[EvidenceChunk] = ...
```

`build_trajectory_from_state` MUST copy `state["intent_trace"]` → `intent_router`.

## MLflow (FR-015)

On each `ask` run:

| Sink | Content |
|------|---------|
| `mlflow.log_params` | `query_intent`, `intent_source`, `source_bias_applied`, optional `router_fallback_reason` |
| Artifact `intent_router.json` | Full `IntentRouterTrace.model_dump()` |
| Artifact `trajectory.json` | Full `TrajectoryRecord` including `intent_router` |

## Fallback rules (FR-014)

| Condition | `intent_source` | `router_fallback_reason` |
|-----------|-----------------|--------------------------|
| `USE_MOCK_LLM=1` | `keyword_fallback` | `mock_llm` |
| Invalid / missing JSON label | `keyword_fallback` | `invalid_label` |
| LLM timeout | `keyword_fallback` | `llm_timeout` |
| Other exception | `keyword_fallback` | `router_error` |

**MUST NOT** set `intent_source=llm` when fallback path was used.

## Contract tests (required)

- `tests/unit/test_intent_router_trace.py`: LLM path populates all required fields
- Same file: forced fallback includes `router_fallback_reason`
- `tests/contract/test_trajectory_router_fields.py`: trajectory JSON schema stable for eval loader

## Evaluation read path

`evaluation.runner` and `trajectory_fidelity_score` MAY assert `trajectory.intent_router is not None` for production ask runs (SC-006).
