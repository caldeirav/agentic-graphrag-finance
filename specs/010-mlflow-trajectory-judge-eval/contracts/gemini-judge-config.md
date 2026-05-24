# Gemini Judge Configuration Contract (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Config**: `configs/judges/gemini_2_5_pro.yaml`  
**Runtime**: `evaluation/judges/gemini_panel.py`

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | yes (prod) | `langchain_google_genai` auth |
| `USE_MOCK_JUDGE` | no | `1` → mock panel (CI) |

Never commit API keys. `.env.example` documents `GOOGLE_API_KEY`.

## Model

```yaml
model: gemini-2.5-pro
temperature: 0.0
judge_config_id: gemini_2_5_pro
```

## Rubrics (FR-012) — extend existing file

Map criterion id → prompt fragment:

| criterion_id | FR-012 name |
|--------------|-------------|
| `trajectory_coherence` | Trajectory completeness & coherence |
| `routing_decisions` | Routing & LLM decision quality |
| `retrieval_fidelity` | Retrieval fidelity |
| `synthesis_grounding` | Synthesis grounding |

Each rubric instructs: score **0.0–1.0**, provide justification, optional `stage` attribution.

## Response contract

Judge MUST return parseable JSON (see `research.md` R5).  
`GeminiJudgePanel` MUST NOT assign hardcoded scores after LLM call.

On parse error: raise retriable `JudgeParseError` for `ask_judge` retry loop.

## Legacy score keys (deprecation)

| Legacy | Maps to |
|--------|---------|
| `value_alignment` | `synthesis_grounding` (approx) |
| `claim_presence` | `synthesis_grounding` |
| `trajectory_fidelity` | `trajectory_coherence` |

Shim for one release in benchmark report reader only.

## Judge status vocabulary (I2)

Canonical `judge_status` values on `JudgeRunSummary` and MLflow tags:

| Value | When |
|-------|------|
| `ok` | Judge completed successfully |
| `degraded` | Judge invoked but failed after max retries |
| `not_evaluable` | Trajectory validation not `complete`; judge not called |

Legacy `failed` / `skipped` MUST NOT appear in new artifacts.

## Mock judge (CI)

When `USE_MOCK_JUDGE=1`:
- `judge_model`: `mock-judge`
- Scores derived from snapshot completeness heuristics
- `configs/trajectory_judge.yaml` `mock_reduced_criteria: true` skips deep synthesis rubric

## Contract tests

- `tests/unit/test_gemini_judge_parser.py` — JSON fixtures, no network
- Optional `@pytest.mark.live` test with `GOOGLE_API_KEY` (not in CI)
