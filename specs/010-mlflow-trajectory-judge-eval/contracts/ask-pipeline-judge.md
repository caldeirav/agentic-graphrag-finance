# Ask Pipeline: Validation + Blocking Judge (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Entry**: `QueryService.answer` / `cli/pipeline.run_ask_pipeline`

## Sequence (FR-009a)

```text
1. traced_query_run start
2. LangGraph invoke (autolog traces)
3. build_agent_trajectory_snapshot(state)
4. log agent_trajectory.json + legacy artifacts (transition)
5. validate_trajectory(snapshot) → log trajectory_validation.json
6. if complete: judge_with_retries(snapshot, answer) → log judge_verdict.json
   else: judge_status=not_evaluable
7. set MLflow tags
8. console trace footer (trajectory_audit)
9. return QueryResponse (includes validation + judge summary fields)
10. traced_query_run end
```

## Retry-then-degrade (FR-009b)

Config: `configs/trajectory_judge.yaml`

```yaml
max_retries: 3
backoff_seconds: [1, 2, 4]
min_score: 0.6
```

On judge failure after retries:
- `judge_status: degraded`
- Log `judge_error.txt` or error field in `judge_verdict.json`
- **Do not** change `QueryStatus` from successful retrieval
- stderr warning one line
- Exclude run from judge aggregates

## Console trace (007 extension)

Event type: `trajectory_audit` (footer)

**normal** depth (≤15 lines total for audit block):
```
validation: complete
judge: ok (gemini-2.5-pro)
  trajectory_coherence: 0.82
  routing_decisions: 0.71  [macro]
  retrieval_fidelity: 0.88
  synthesis_grounding: 0.55  ← below 0.6
weakest: synthesis_grounding @ synthesis
```

**verbose**: include truncated justifications.

## QueryResponse extension

Add optional fields (Pydantic):
- `validation_status`
- `judge_status`
- `judge_scores: dict[str, float]`

## Benchmark parity

`evaluation/runner.py` MUST use the same `run_post_query_audit()` path after each item so production and benchmark judge behavior match.

## Contract tests

- `tests/integration/test_ask_judge_mlflow.py` — mock judge, assert artifact order
- `tests/integration/test_agent_query_ask.py` — extend for footer presence when `--trace normal`
