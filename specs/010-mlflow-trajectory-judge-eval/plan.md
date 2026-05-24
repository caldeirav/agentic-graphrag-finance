# Implementation Plan: Auditable MLflow Trajectories & LLM-as-Judge Evaluation

**Branch**: `010-mlflow-trajectory-judge-eval` | **Date**: 2026-05-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-mlflow-trajectory-judge-eval/spec.md` with technical mandates for MLflow agent tracing (primary), blocking LLM-as-judge, Gemini via `GOOGLE_API_KEY`, deterministic validator, and 90% reference-suite gate.

## Summary

Extend observability and evaluation so every production `ask` and benchmark item produces an **MLflow Trace** (LangGraph/LangChain autolog) as the operator drill-down surface, a **derived `agent_trajectory.json` snapshot** for validator/judge/CI, a **deterministic trajectory validator** (`complete` | `incomplete` | `non_reproducible`), and a **blocking Gemini judge** (four criteria, 0.0–1.0, retry-then-degrade) logged on the same MLflow run with console summary via the 007 trace registry.

## Technical Context

**Language/Version**: Python 3.12+ (project standard via `pyproject.toml`)

**Primary Dependencies**: MLflow 3.x (`mlflow.langchain.autolog`), LangGraph, LangChain, `langchain-google-genai` (Gemini judge), Pydantic v2, Rich (console trace), existing `src/tracing/mlflow_langgraph.py` and `src/evaluation/judges/gemini_panel.py`

**Storage**: MLflow tracking (`MLFLOW_TRACKING_URI`, default `sqlite:///mlflow.db` per `configs/mlflow.yaml`); artifacts: Trace spans + `agent_trajectory.json`, `trajectory_validation.json`, `judge_verdict.json` (names per contracts)

**Testing**: pytest — contract tests for schema/validator/import boundary; integration tests for ask+benchmark MLflow artifacts; fixture-based validator suite; CI uses `USE_MOCK_JUDGE=1`

**Target Platform**: Local CLI (`agent-query ask`, `agent-query test` / eval runner); MLflow UI for inspection

**Project Type**: CLI + library layers (`retrieval/`, `tracing/`, `evaluation/`)

**Performance Goals**: Accept blocking judge latency on production `ask` in v1 (spec assumption); judge retries with exponential backoff (max 3); derived JSON export & validation &lt; 500ms typical

**Constraints**:
- Evaluation module MUST NOT import `retrieval`, `ingestion`, or `graph` packages (SC-004)
- `GOOGLE_API_KEY` from `.env` only; `USE_MOCK_JUDGE=1` for CI
- Judge model: `configs/judges/gemini_2_5_pro.yaml` → `gemini-2.5-pro`
- Alert threshold: `configs/trajectory_judge.yaml` → `min_score: 0.6` (configurable)

**Scale/Scope**: Reference suite ≥50 items (gold-path + macro-binding + new trajectory-validation fixtures) on fixed AAPL corpus; extend existing partial artifacts (`trajectory.json`, `macro_binding.json`, `navigation_trace.json`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Judge criteria include synthesis grounding; trajectory records evidence hashes | **PASS** — FR-012 synthesis grounding + FR-005 evidence hashes in `agent_trajectory.json` |
| **II. Structural Semantics Preservation** | No parser changes in this feature | **PASS** — N/A (consumes existing graph/chunk refs) |
| **III. Traceability** | MLflow Trace primary; plan/route/hops/evidence in derived snapshot | **PASS** — research.md + `contracts/trajectory-schema.md` |
| **IV. Separation of Concerns** | Validator/judge in `evaluation/`; trace export hook in `tracing/`; orchestration emits state only | **PASS** — `contracts/judge-eval-boundary.md` |
| **V. Code Health & Environment Stability** | Pydantic models for validation/judge results; `uv` lockfile | **PASS** — `data-model.md` |
| **VI. Rigorous Agent Evaluation** | External Gemini judge on trajectories; modular benchmark gate | **PASS** — extends `evaluation/runner.py` + new fixtures |

**Post-design re-check**: Phase 1 contracts preserve layer boundaries. **Exception documented** below: Constitution IV default (“eval not on hot path”) vs spec FR-009a (blocking judge on every `ask`) — intentional product requirement for v1 auditability.

## Project Structure

### Documentation (this feature)

```text
specs/010-mlflow-trajectory-judge-eval/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── query.py              # Extend TrajectoryRecord → AgentTrajectorySnapshot
│   └── evaluation.py         # TrajectoryValidationResult, JudgeCriterionResult, JudgeRunSummary
├── tracing/
│   ├── mlflow_langgraph.py   # Trace-linked spans, export agent_trajectory.json, log judge tags
│   └── console_trace/        # Footer: validation + judge summary (007 extension)
├── evaluation/
│   ├── validator/            # NEW: deterministic trajectory validator
│   ├── judges/
│   │   └── gemini_panel.py   # Structured JSON parsing, four FR-012 criteria
│   ├── runner.py             # Benchmark batch + gate aggregation
│   └── ask_judge.py          # NEW: blocking judge orchestration (retries, degrade)
├── retrieval/
│   └── service.py            # Post-graph: validate → judge → finalize response
└── cli/
    └── pipeline.py           # Wire ask pipeline to judge hook

configs/
├── mlflow.yaml
├── trajectory_judge.yaml     # NEW: thresholds, retries, criterion ids
└── judges/gemini_2_5_pro.yaml

tests/
├── contract/
│   ├── test_trajectory_schema.py
│   ├── test_judge_import_boundary.py
│   └── test_trajectory_validator.py
├── fixtures/trajectory_validation/   # NEW: broken + valid snapshots
└── integration/
    ├── test_ask_judge_mlflow.py
    └── test_benchmark_trajectory_gate.py
```

**Structure Decision**: Single Python package layout; new code under `evaluation/validator/` and `tracing/` export helpers; minimal changes to LangGraph nodes (span attributes only where autolog gaps exist).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Blocking judge on production `ask` hot path (Constitution IV default) | Spec FR-009a / SC-007 require judge artifacts before CLI completion; **authorized** under constitution v1.2.1 production audit hook exception | Offline-only judge misses operator debugging and violates clarified acceptance scenarios |
| Dual storage (MLflow Trace + JSON snapshot) | Trace UI for humans; JSON for import-boundary-safe eval | Trace-only blocks deterministic validator in CI without MLflow server coupling |
| Retry-then-degrade on judge failure | Spec FR-009b — availability vs audit completeness | Hard-fail judge would block answers on transient Gemini outages |

## Gap Analysis (current code → target)

| Area | Current | Target (010) |
|------|---------|----------------|
| **Observability sink** | `trajectory.json` from `build_trajectory_from_state` + side artifacts; autolog best-effort | MLflow Trace **primary**; `agent_trajectory.json` v1 derived export with `schema_version` |
| **Trajectory schema** | `TrajectoryRecord` lacks version, structured plan (intent/steps/rationale), hop `edge_id`/`edge_type`, synthesis path | Full FR-002–FR-005 fields per `contracts/trajectory-schema.md` |
| **Validator** | None | `evaluation/validator/` → `TrajectoryValidationResult` |
| **Judge on ask** | Only benchmark `evaluation/runner.py` | Blocking hook in `QueryService.answer` after validation |
| **GeminiJudgePanel** | Placeholder scores (`0.8`, `0.7`); legacy rubric keys | Parse JSON with four FR-012 criteria + stage attribution |
| **Console trace** | Stage panels; no validation/judge footer | FR-013 compact summary (&lt;15 lines at `normal`) |
| **90% gate** | Partial gold-path / macro suites | Combined reference suite ≥50 items + CI gate script |

## Implementation Phases (for tasks.md)

### Phase A — Schema & export (P1)
- Define `AgentTrajectorySnapshot` v1 and `build_agent_trajectory_snapshot(state, trace_id?)` in `tracing/`
- Log `agent_trajectory.json`; tag run with `trajectory_schema_version`
- Ensure LangGraph compile uses autolog; add `@mlflow.trace` or span names for macro/intent/meso/micro/synthesize if autolog gaps

### Phase B — Validator (P1)
- Implement rule engine per `contracts/trajectory-validator.md`
- Unit tests on fixtures (complete, incomplete, non_reproducible)

### Phase C — Judge (P2)
- `configs/trajectory_judge.yaml` + extend `gemini_2_5_pro.yaml` rubrics for four criteria
- `ask_judge.py`: retry/backoff, `JudgeRunSummary`, MLflow `judge_verdict.json` + tags
- Import-boundary test (AST or import-linter)

### Phase D — Ask & console integration (P2)
- `QueryService`: validate → judge (blocking) → return; degraded path
- Console trace footer payload + registry extension (007)

### Phase E — Benchmark gate (P2)
- Merge fixtures to ≥50 items; `test_benchmark_trajectory_gate.py`; report exclusion counts

### Phase F — MLflow operator UX (P3)
- Document Trace + artifact drill-down in quickstart; optional `mlflow.genai.evaluate` scorers only if simpler than custom panel (see research.md)

## Dependencies

- **007** ask console trace — footer extension
- **008** macro trajectory — `macro_binding.json` folded into snapshot
- **009** navigation trajectory — hops in snapshot
- **001** evaluation boundaries — reaffirmed in contracts

## Artifacts Generated

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |
