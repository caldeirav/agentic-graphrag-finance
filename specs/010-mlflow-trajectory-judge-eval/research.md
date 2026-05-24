# Research: Auditable MLflow Trajectories & LLM-as-Judge (010)

**Feature**: 010-mlflow-trajectory-judge-eval | **Date**: 2026-05-24

## R1 — Authoritative observability: MLflow Trace vs JSON

**Decision**: **MLflow Trace spans are primary** for operator drill-down; **`agent_trajectory.json` v1 is a derived, versioned snapshot** assembled from LangGraph final state + normalized side artifacts (`macro_binding.json`, `navigation_trace.json`, `intent_router.json`) + optional trace correlation id.

**Rationale**:
- Spec clarifications and [MLflow agent tracing](https://mlflow.org/llm-tracing/#agent-tracing) align with existing `mlflow.langchain.autolog()` in `configure_mlflow()` (`src/tracing/mlflow_langgraph.py`).
- Evaluation layer cannot depend on live graph/retrieval imports (SC-004); judges and validators need a stable file payload in CI.
- Current `trajectory.json` is incomplete vs FR-002–FR-005 — rename/version bump avoids silent schema drift.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| JSON-only (no Trace) | Loses LLM I/O span drill-down required by FR-015 |
| Trace-only (no JSON) | Blocks offline validator/judge without MLflow API in unit tests |
| Duplicate manual spans only | High maintenance; autolog already captures LangChain LLM calls |

**Implementation note**: Keep logging `macro_binding.json` etc. for backward compatibility until 011 migration; `agent_trajectory.json` subsumes them logically via `build_agent_trajectory_snapshot()`.

---

## R2 — Stage-linked spans (macro, intent, meso, micro, synthesize)

**Decision**: Rely on **`mlflow.langchain.autolog()`** for LLM spans; add **explicit run tags and artifact milestones** per stage; where LangGraph node names are not visible in Trace UI, wrap node entry with `mlflow.update_current_trace()` / `@mlflow.trace(span_type=CHAIN)` on thin adapters in `retrieval/orchestration/nodes/*` (minimal touch).

**Rationale**: FR-001 requires trace-linked spans per stage; autolog covers synthesis/intent LLM calls but not deterministic graph hops.

**Alternatives considered**:
- Full OpenTelemetry manual instrumentation — heavier than needed for v1.
- Single monolithic span — fails FR-015 stage attribution.

---

## R3 — LLM-as-judge integration pattern

**Decision**: **Custom `GeminiJudgePanel` extended** to emit structured JSON for four FR-012 criteria; log via `MlflowClient.log_dict` as `judge_verdict.json` and MLflow tags (`judge_status`, `judge_weakest_stage`, per-criterion scores). **Do not require `mlflow.genai.evaluate` batch API** for blocking per-ask path in v1.

**Rationale**:
- [MLflow LLM-as-a-judge](https://mlflow.org/llm-as-a-judge) patterns are satisfied by persisted scores + justifications on the run; batch `genai.evaluate` fits benchmark sweeps later.
- Existing `GeminiJudgePanel` + `configs/judges/gemini_2_5_pro.yaml` already target Gemini; migration is prompt + parser, not new provider.
- Blocking `ask` needs synchronous invoke with retries — runner pattern maps cleanly.

**Alternatives considered**:
| Alternative | When to revisit |
|-------------|-----------------|
| `mlflow.genai.evaluate` with registered scorers | Phase F if benchmark batch deduplication is needed |
| Separate judge microservice | Overkill for CLI tool |

---

## R4 — Gemini credentials and model

**Decision**: Production judge uses **`ChatGoogleGenerativeAI`** with model from `configs/judges/gemini_2_5_pro.yaml` (`gemini-2.5-pro`), credentials from **`GOOGLE_API_KEY`** in `.env` (read by langchain-google-genai). **`USE_MOCK_JUDGE=1`** in CI returns deterministic scores for four criteria with `judge_model=mock-judge`.

**Rationale**: Matches `.env.example` and existing panel; no secrets in repo.

**Alternatives considered**: Vertex AI / service account — not in current stack; would need new env vars and dependency.

---

## R5 — Judge prompt and score parsing

**Decision**: Judge prompt includes serialized **`agent_trajectory.json`** (truncated if needed) + final answer text + question; require **JSON-only response**:

```json
{
  "criteria": [
    {"id": "trajectory_coherence", "score": 0.85, "stage": null, "justification": "..."},
    {"id": "routing_decisions", "score": 0.72, "stage": "macro", "justification": "..."},
    {"id": "retrieval_fidelity", "score": 0.90, "stage": "micro", "justification": "..."},
    {"id": "synthesis_grounding", "score": 0.65, "stage": "synthesis", "justification": "..."}
  ],
  "overall_summary": "..."
}
```

Parse with `json.loads` + Pydantic validation; on parse failure, retry (FR-009b). Map legacy keys (`value_alignment`, etc.) only in migration shim for old benchmark reports.

**Rationale**: Current `GeminiJudgePanel` assigns hardcoded `0.8` scores — must be replaced for FR-010/FR-012.

---

## R6 — Blocking judge on `ask` with retry-then-degrade

**Decision**: In `QueryService.answer`, after graph invoke and snapshot export: **(1)** run validator → **(2)** if `complete`, run judge with up to **3 retries** (exponential backoff from `configs/trajectory_judge.yaml`) → **(3)** on exhaustion set `judge_status=degraded`, log error artifact, exclude from aggregates, print console warning; **do not change** successful `QueryStatus` from retrieval. If validation ≠ `complete`, set `judge_status=not_evaluable` (canonical enum: `ok` \| `degraded` \| `not_evaluable` only).

**Rationale**: Spec FR-009a/FR-009b; constitution hot-path exception documented in plan.

**Alternatives considered**: Async judge — rejected for v1 (operators need scores before footer).

---

## R7 — Trajectory validator

**Decision**: Pure-Python rule engine in `evaluation/validator/trajectory.py` consuming **`AgentTrajectorySnapshot`** only. Status enum: `complete` | `incomplete` | `non_reproducible` with `reason_codes[]` (machine-readable).

**Rationale**: Deterministic, fast, testable; no LLM for structural validation.

**Key rules** (non-exhaustive; see contract):
- Missing `schema_version`, empty `document_route` on successful numeric/qualitative ask → `incomplete`
- Evidence without `content_hash` → `incomplete`
- Hop `node_id` not prefixed by any route accession → `non_reproducible`
- Hop missing `node_type` → `incomplete`
- Macro failure: empty graph/evidence allowed with `absent_reason` codes

---

## R8 — Reference suite for 90% gate

**Decision**: **Combined in-repo slice**:
- Existing gold-path JSONL items (subset)
- Existing macro-binding fixtures
- **New** `tests/fixtures/trajectory_validation/*.json` (intentionally broken + golden complete snapshots)

Minimum **50** items; fixed issuer **AAPL** materialized snapshot id pinned in benchmark config.

**Rationale**: Spec clarification; reuses 008/009 investments.

---

## R9 — Console trace extension (007)

**Decision**: Add trace stage/footer event `trajectory_audit` with fields: `validation_status`, `validation_reason_codes` (truncated), `judge_status`, four criterion scores, `weakest_criterion`, `weakest_stage`. Emit only at `normal`/`verbose`; cap **15 lines** at `normal` (FR-013 / SC-006).

**Rationale**: Extends registry per 007 contracts; no duplicate Rich renderer.

---

## R10 — Config files

**Decision**:
- `configs/trajectory_judge.yaml` — `min_score: 0.6`, `max_retries: 3`, `backoff_seconds: [1, 2, 4]`, criterion ids, mock_reduced_criteria flag
- `configs/judges/gemini_2_5_pro.yaml` — model, temperature, per-criterion rubric text (extend existing file)

**Rationale**: FR-013 configurable threshold; single place for retry policy.

---

## Resolved NEEDS CLARIFICATION

All technical context items resolved; no open NEEDS CLARIFICATION for Phase 1.
