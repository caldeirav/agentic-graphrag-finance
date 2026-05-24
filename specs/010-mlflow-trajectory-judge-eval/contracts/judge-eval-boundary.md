# Judge & Evaluation Import Boundary (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Constitution**: Principle IV, SC-004

## Rule (NON-NEGOTIABLE)

Modules under `src/evaluation/` MUST NOT import:

- `retrieval` (including `retrieval.orchestration`, `retrieval.macro`, `retrieval.navigation`)
- `ingestion`
- `graph`
- `parsing`

**Allowed imports**:
- `models.*` (Pydantic DTOs)
- `contracts.*` (public facades only if needed for types)
- `tracing.mlflow_langgraph` — **logging helpers only** (`setup_mlflow`, `log_judge_verdict`); NOT `build_trajectory_from_state` from retrieval path
- Standard library, MLflow, LangChain Google GenAI for judge LLM only

## Judge inputs

The judge receives **only**:

1. `AgentTrajectorySnapshot` (dict or model) — serialized JSON
2. `AnswerPackage.text` (+ optional citations list)
3. `BenchmarkItem` or ask metadata (`question`, optional `ground_truth`)

No live graph queries, no re-fetching chunks.

## Orchestration boundary

| Layer | Calls |
|-------|-------|
| `retrieval/service.py` | Graph invoke → export snapshot → **call** `evaluation.validator.validate(snapshot)` → **call** `evaluation.ask_judge.run(snapshot, answer)` |
| `evaluation/` | Never calls back into retrieval |

Facade for ask hook (new):

```python
def run_post_query_audit(
    snapshot: AgentTrajectorySnapshot,
    answer: AnswerPackage | None,
    *,
    question: str,
    mlflow_run_id: str,
) -> tuple[TrajectoryValidationResult, JudgeRunSummary]:
    ...
```

Implemented in `evaluation/`; imported by `retrieval/service.py` only.

## CI enforcement

- `tests/contract/test_judge_import_boundary.py` — AST walk or import-linter contract
- Fails build on forbidden imports in `src/evaluation/`

## Mock mode

`USE_MOCK_JUDGE=1`:
- Skips `ChatGoogleGenerativeAI`
- Returns four criterion scores from fixture heuristics
- Documented reduced rubric depth in `configs/trajectory_judge.yaml`

## MLflow alignment

Judge results logged per [LLM-as-a-judge](https://mlflow.org/llm-as-a-judge) patterns:
- Structured scores artifact
- Human-readable justifications
- Same `run_id` as trajectory

Custom panel is acceptable for v1; `mlflow.genai.evaluate` optional for batch benchmarks only.
