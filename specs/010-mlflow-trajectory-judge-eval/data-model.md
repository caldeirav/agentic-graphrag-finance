# Data Model: Trajectory, Validation & Judge (010)

**Feature**: 010-mlflow-trajectory-judge-eval | **Date**: 2026-05-24

## Entity relationship

```text
QueryExecution
  ├── mlflow_run_id
  ├── mlflow_trace_id (optional correlation)
  ├── AgentTrajectorySnapshot (artifact: agent_trajectory.json)
  ├── TrajectoryValidationResult (artifact: trajectory_validation.json)
  ├── JudgeRunSummary (artifact: judge_verdict.json)
  └── AnswerPackage

BenchmarkItem → (same bundle per item)
EvaluationRun → aggregates over complete trajectories only
```

## AgentTrajectorySnapshot

**Purpose**: Versioned derived audit record (FR-001a). Supersedes logical content of `TrajectoryRecord` + side artifacts.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | `str` | yes | e.g. `"1.0.0"`; bump on breaking change (FR-016) |
| `query_id` | `str` | no | UUID if available |
| `query_text` | `str` | yes | Truncated in logs if needed |
| `issuer_id` | `str` | yes | |
| `snapshot_id` | `str` | yes | |
| `mlflow_run_id` | `str` | yes | |
| `mlflow_trace_id` | `str` | no | Link to Trace UI |
| `status` | `QueryStatus` | yes | Graph outcome |
| `synthesis_path` | `enum` | yes | `live_llm` \| `deterministic_fallback` \| `template` |
| `plan` | `TrajectoryPlan` | yes | May be partial on macro failure |
| `document_route` | `list[FilingRouteEntry]` | yes | Empty only with `absent_reason` |
| `graph_traversal` | `list[GraphHop]` | yes | Ordered |
| `evidence` | `list[EvidenceEntry]` | yes | All shortlisted chunks, not only prompt subset |
| `stage_timings_ms` | `dict[str, int]` | no | macro, intent, meso, micro, synthesis |
| `macro_binding` | `dict` | no | 008 payload mirror |
| `navigation_trace` | `dict` | no | 009 payload mirror |
| `intent_router` | `IntentRouterTrace` | no | 005/007 |

### TrajectoryPlan

| Field | Type | Required |
|-------|------|----------|
| `intent_summary` | `str` | yes |
| `steps_considered` | `list[StageDecision]` | no |
| `chosen_path_rationale` | `str` | yes |
| `rejected_alternatives` | `list[str]` | no |

### StageDecision

| Field | Type | Required |
|-------|------|----------|
| `stage` | `str` | yes | macro \| intent \| meso \| micro \| synthesis |
| `description` | `str` | yes | e.g. ranked sections |
| `selected` | `bool` | no |

### FilingRouteEntry

| Field | Type | Required |
|-------|------|----------|
| `accession` | `str` | yes |
| `form_type` | `str` | yes |
| `period_end` | `str` | no | ISO date |
| `fiscal_period_label` | `str` | no |

### GraphHop

| Field | Type | Required |
|-------|------|----------|
| `hop_index` | `int` | yes |
| `stage` | `str` | yes |
| `node_id` | `str` | yes |
| `node_type` | `str` | yes |
| `edge_id` | `str` | no | Required when edge exists |
| `edge_type` | `str` | yes | Catalog edge type |
| `accession_prefix` | `str` | yes | Denormalized for validator |

### EvidenceEntry

| Field | Type | Required |
|-------|------|----------|
| `chunk_node_id` | `str` | yes |
| `content_hash` | `str` | yes | Stable SHA-256 or project standard |
| `citation_label` | `str` | yes |
| `source_type` | `str` | yes | numeric \| narrative |
| `accession` | `str` | yes |
| `section_id` | `str` | no |
| `in_prompt` | `bool` | yes | FR edge case: budget truncation |

### Absent sections (macro failure)

Use standardized `absent_reason` on empty `graph_traversal` / `evidence`:
- `macro_binding_failed`
- `scope_error`
- `insufficient_evidence`
- `not_applicable`

## TrajectoryValidationResult

| Field | Type | Required |
|-------|------|----------|
| `schema_version` | `str` | yes |
| `status` | `ValidationStatus` | yes | `complete` \| `incomplete` \| `non_reproducible` |
| `reason_codes` | `list[ValidationReason]` | yes |
| `validated_at` | `datetime` | yes |
| `snapshot_schema_version` | `str` | yes |

### ValidationReason

| Field | Type |
|-------|------|
| `code` | `str` | e.g. `MISSING_CONTENT_HASH` |
| `field` | `str` | JSON pointer–style path |
| `message` | `str` |

## JudgeCriterionResult

| Field | Type | Required |
|-------|------|----------|
| `criterion_id` | `str` | yes | See FR-012 ids |
| `score` | `float` | yes | 0.0–1.0 inclusive |
| `justification` | `str` | yes |
| `stage` | `str` | no | macro \| intent \| meso \| micro \| synthesis |

**Criterion IDs** (stable):
- `trajectory_coherence`
- `routing_decisions`
- `retrieval_fidelity`
- `synthesis_grounding`

## JudgeRunSummary

| Field | Type | Required |
|-------|------|----------|
| `judge_model` | `str` | yes |
| `judge_config_id` | `str` | yes | e.g. `gemini_2_5_pro` |
| `judge_status` | `JudgeStatus` | yes | `ok` \| `degraded` \| `skipped` \| `not_evaluable` |
| `criteria` | `list[JudgeCriterionResult]` | yes |
| `overall_summary` | `str` | no |
| `weakest_criterion_id` | `str` | no |
| `weakest_stage` | `str` | no |
| `retry_count` | `int` | yes |
| `error` | `str` | no | When degraded |

### JudgeStatus transitions

```text
validation=complete → judge invoked → ok | degraded (retries exhausted)
validation≠complete → skipped (not_evaluable)
USE_MOCK_JUDGE=1 → ok with mock-judge model id
```

## BenchmarkFidelityAggregate

| Field | Type |
|-------|------|
| `suite_name` | `str` |
| `total_items` | `int` |
| `complete_trajectories` | `int` |
| `incomplete_count` | `int` |
| `non_reproducible_count` | `int` |
| `judge_degraded_count` | `int` |
| `pass_rate_validation` | `float` | complete / total |
| `mean_scores` | `dict[criterion_id, float]` | over complete + judged ok only |
| `gate_passed` | `bool` | pass_rate ≥ 0.9 |

## RunCorrelationBundle

Emitted in CLI `--json` and MLflow tags:

| Field | Type |
|-------|------|
| `mlflow_run_id` | `str` |
| `trajectory_uri` | `str` |
| `validation_status` | `str` |
| `judge_status` | `str` |
| `judge_scores` | `dict[str, float]` |

## Migration from TrajectoryRecord

| Legacy (`TrajectoryRecord`) | New (`AgentTrajectorySnapshot`) |
|----------------------------|--------------------------------|
| `plan: MacroPlan` | `plan.intent_summary` + binding rationale |
| `document_route: list[FilingRef]` | `FilingRouteEntry` enriched |
| `graph_traversal: GraphVisit` | `GraphHop` (+ edge_id, node_type) |
| `evidence: EvidenceChunk` | `EvidenceEntry` (+ in_prompt) |
| — | `schema_version`, `synthesis_path` |

`TrajectoryRecord` remains for backward compatibility one release; `build_trajectory_from_state` delegates to snapshot builder.

## Pydantic module placement

- Extend `src/models/query.py` or add `src/models/trajectory.py` for snapshot/validation types
- Extend `src/models/evaluation.py` for `JudgeCriterionResult`, `JudgeRunSummary`, `TrajectoryValidationResult`
