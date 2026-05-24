# Quickstart: MLflow Trajectories & LLM-as-Judge (010)

**Feature**: 010-mlflow-trajectory-judge-eval | **Branch**: `010-mlflow-trajectory-judge-eval`

## Prerequisites

```bash
uv sync --locked
```

`.env` (minimum for live judge):

```env
GOOGLE_API_KEY=your_gemini_api_key_here
USE_MOCK_JUDGE=0
USE_MOCK_LLM=0
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3.6-35b-a3b
SEC_EDGAR_USER_AGENT=Your Name your.email@example.com
```

Materialized issuer corpus (example AAPL):

```bash
uv run agent-query materialize --ticker AAPL
# Note snapshot_id from output
```

## 1. Production ask with trace + judge

```bash
uv run agent-query ask \
  --ticker AAPL \
  --snapshot-id <SNAPSHOT_ID> \
  --trace normal \
  --query "What was Apple's net sales year over year?"
```

**Expected**:
- stderr: stage panels (007) + **trajectory audit footer** (validation status, four judge scores 0.0–1.0, weakest stage if any &lt; 0.6)
- stdout: grounded answer
- MLflow run with Trace + artifacts

## 2. Inspect MLflow

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Open experiment `sec-disclosure-rag` → latest run:

| Surface | What to check |
|---------|----------------|
| **Traces** tab | Spans for macro/intent/meso/micro/synthesis LLM calls |
| **Artifacts** | `agent_trajectory.json`, `trajectory_validation.json`, `judge_verdict.json` |
| **Tags** | `validation_status`, `judge_status`, `judge_weakest_stage` |

## 3. CI / offline judge (mock)

```bash
USE_MOCK_JUDGE=1 uv run pytest tests/contract/test_trajectory_validator.py -q
USE_MOCK_JUDGE=1 uv run pytest tests/integration/test_ask_judge_mlflow.py -q
```

## 4. Benchmark + 90% gate

```bash
USE_MOCK_JUDGE=1 uv run agent-query test --gold-path
# After implementation:
uv run python -m evaluation.cli run-suite \
  --suite reference_trajectory_gate \
  --snapshot-id <SNAPSHOT_ID>
```

Gate fails when `complete` trajectories &lt; 90% of ≥50 reference items.

## 5. Live Gemini judge smoke

```bash
USE_MOCK_JUDGE=0 GOOGLE_API_KEY=$GOOGLE_API_KEY \
  uv run agent-query ask \
  --ticker AAPL \
  --snapshot-id <SNAPSHOT_ID> \
  --trace normal \
  --query "Summarize risk factors in the latest 10-K."
```

Verify `judge_verdict.json` contains four criteria with non-placeholder scores and justifications.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `judge_status=degraded` | Gemini quota/key; see `judge_verdict.json` `error`; 3 retries in logs |
| `validation_status=incomplete` | `trajectory_validation.json` `reason_codes` |
| No Trace tab | `configs/mlflow.yaml` `autolog_langchain: true`; MLflow ≥ 3.x |
| Placeholder judge scores (0.8, 0.7) | Pre-010 code path — upgrade branch |

## Config reference

- `configs/mlflow.yaml` — tracking URI, experiment, autolog
- `configs/trajectory_judge.yaml` — `min_score`, retries (after implement)
- `configs/judges/gemini_2_5_pro.yaml` — `gemini-2.5-pro` model + rubrics
