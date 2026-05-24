# MLflow Trace & Export Contract (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Primary UI**: MLflow Trace ([agent tracing](https://mlflow.org/llm-tracing/#agent-tracing))

## Responsibilities

| Component | Package | Role |
|-----------|---------|------|
| Autolog | `tracing/mlflow_langgraph.py` | `mlflow.langchain.autolog()` on configure |
| Run wrapper | `traced_query_run()` | One MLflow run per ask/benchmark item |
| Snapshot export | `tracing/trajectory_export.py` (new) | `build_agent_trajectory_snapshot(state) → AgentTrajectorySnapshot` |
| Artifact log | `log_agent_trajectory()`, `log_validation()`, `log_judge_verdict()` | MlflowClient.log_dict |

## Trace-primary flow

```text
LangGraph invoke
  → mlflow.langchain.autolog captures LLM spans
  → optional @mlflow.trace on node adapters (macro, intent, meso, micro, synthesize)
  → final state
  → build_agent_trajectory_snapshot(state, trace_id?)
  → log agent_trajectory.json
  → validator (evaluation/) reads snapshot only
  → judge (evaluation/) reads snapshot + answer
  → log trajectory_validation.json, judge_verdict.json
  → set tags on run
```

## Required MLflow run tags

| Tag | Example |
|-----|---------|
| `trajectory_schema_version` | `1.0.0` |
| `validation_status` | `complete` |
| `judge_status` | `ok` |
| `judge_weakest_criterion` | `synthesis_grounding` |
| `judge_weakest_stage` | `synthesis` |

Per-criterion scores MAY be tags `judge_score_<criterion_id>` for UI filtering.

## Span naming convention

When manual spans are added, names MUST be:

- `stage.macro`
- `stage.intent`
- `stage.meso`
- `stage.micro`
- `stage.synthesize`

Attributes SHOULD include `snapshot_id`, `issuer_id`, and stage-specific ids (e.g. `accession`).

## Correlation

`AgentTrajectorySnapshot.mlflow_trace_id` SHOULD be set from `mlflow.get_last_active_trace_id()` when available so operators jump from JSON artifact to Trace UI.

## Failure modes

| Case | Trace | Snapshot | Validation |
|------|-------|----------|------------|
| Macro bind fail | Partial spans | Emitted with absent sections | May be `complete` if failure well-documented |
| Graph abort | Partial | Emitted | `incomplete` or `complete` per rules |
| MLflow down | Local stderr only | Still build snapshot; warn if log fails | N/A |

## Contract tests

- `tests/integration/test_ask_judge_mlflow.py` — run produces Trace + three artifacts
- `tests/unit/test_trajectory_export.py` — snapshot from fixture state matches schema
- **`tests/integration/test_mlflow_trace_spans.py`** (required) — mock `ask` asserts an MLflow Trace exists for the run and at least one span is present (FR-001 smoke); fails if autolog disabled
