# Implementation Plan: Autonomous Macro Routing

**Branch**: `008-autonomous-macro-routing` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)

**Input**: Autonomous macro routing — NL temporal mapping, LLM proposal + deterministic validation, YoY/QoQ pairing, fail-closed misalignment, durable trajectory, FinAgentBench macro eval slice (70%/80% gates).

## Summary

Refactor filing selection so **`macro_router`** is the authoritative stage for natural-language temporal scope when CLI flags are absent: an **LLM macro planner** proposes anchors/comparison/accessions, a **deterministic validator** enforces manifest-backed YoY/QoQ pairing and fail-closed misalignment rules, and **`macro_binding.json`** plus console trace capture every decision. **CLI-resolved scope** continues via `bind_filings_for_query()` but no longer passes the full snapshot as “pre-bound” when scope is empty; explicit flags still win via validator precedence. **Evaluation** adds a ≥50-item **`macro_binding.jsonl`** slice scored independently of answer text.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Primary dependencies** (existing): `langgraph`, `langchain-openai`, `pydantic`, `typer`, `mlflow`, `rich` (007 trace)

**Reuse**:

| Module | Role |
|--------|------|
| `retrieval/temporal.py` | `resolve_temporal_scope`, `fiscal_period_label`, anchor table |
| `retrieval/orchestration/nodes/macro_router.py` | Refactor to planner → validator pipeline |
| `cli/corpus_pipeline.py` | Handoff: empty scope → defer binding to macro |
| `retrieval/service.py` | Macro failure → scope error response |
| `tracing/mlflow_langgraph.py` | + `log_macro_binding()` artifact |
| `tracing/console_trace` + `trace_payloads.py` | Richer macro_router payload |
| `evaluation/registry.py` + `finagentbench.py` | Macro binding eval slice |
| `models/query.py`, `models/corpus.py` | Extend MacroPlan / binding types |

**New modules**:

| Module | Role |
|--------|------|
| `src/retrieval/macro/planner.py` | LLM JSON `MacroBindingProposal` |
| `src/retrieval/macro/validator.py` | Pairing rules, misalignment, CLI precedence |
| `src/retrieval/macro/pairing.py` | YoY/QoQ accession materialization from manifest |
| `src/retrieval/macro/models.py` | `MacroBindingProposal`, `BindingValidationResult` |
| `configs/macro_phrases.yaml` | Phrase catalog for prompt + labels |
| `evaluation/metrics/macro_binding.py` | Set-equality accuracy metric |
| `data/benchmarks/finagentbench/macro_binding.jsonl` | Labeled slice |

**Testing**: `pytest` — validator unit (no LLM), planner mock, corpus handoff contract, trajectory schema, integration benchmark gate, ask fail-closed scenarios.

**Performance goals**:

- Validator < 50 ms for ≤ 10 filings
- One LLM call on autonomous path only (same as today when not pre-bound)
- `--trace normal` macro panel includes validation without > 10% ask overhead

**Constraints**:

- No change to meso/micro ranking logic
- Validator MUST be deterministic (constitution I + clarification Q3)
- Benchmark cases MUST include structured `expected_bindings` (003 contract)

**Scale/Scope**: ~8 source files touched, ~5 new modules, 1 config, 1 JSONL dataset (≥50 rows), extends existing ask + eval paths.

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Fail-closed macro; no SUCCESS with wrong filings; scope error instead of fabricated metrics |
| **II. Structural Semantics Preservation** | PASS | No parsing/graph changes |
| **III. Traceability** | PASS | `macro_binding.json` + trajectory fields; console trace parity (contracts/macro-trajectory.md) |
| **IV. Separation of Concerns** | PASS | Macro logic in `retrieval/macro/`; eval metrics in `evaluation/`; CLI only passes scope hints |
| **V. Code Health & Environment Stability** | PASS | Pydantic models; `uv.lock`; contract tests |
| **VI. Rigorous Agent Evaluation** | PASS | FinAgentBench slice; filing-set accuracy metric independent of answer judge |

**Post-design re-check**: Contracts define validator API, trajectory schema, eval harness — no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-autonomous-macro-routing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── macro-binding-validator.md
│   ├── macro-planner-llm.md
│   ├── macro-trajectory.md
│   └── macro-eval-harness.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source (repository root)

```text
src/
├── retrieval/
│   ├── macro/                    # NEW package
│   │   ├── models.py
│   │   ├── planner.py
│   │   ├── validator.py
│   │   └── pairing.py
│   ├── temporal.py               # reuse anchors; optional helper exports
│   └── orchestration/
│       ├── nodes/macro_router.py   # orchestrate planner + validator
│       └── trace_payloads.py       # extend macro payload
├── cli/corpus_pipeline.py          # empty-scope handoff
├── tracing/mlflow_langgraph.py     # macro_binding artifact
└── evaluation/
    └── metrics/macro_binding.py    # NEW

configs/macro_phrases.yaml          # NEW

data/benchmarks/finagentbench/
└── macro_binding.jsonl             # NEW (≥50 items)

tests/
├── unit/test_macro_validator*.py
├── unit/test_macro_pairing.py
├── contract/test_macro_trajectory_schema.py
├── integration/test_macro_binding_benchmark.py
└── integration/test_ask_macro_fail_closed.py
```

**Structure Decision**: New `retrieval/macro/` subpackage keeps validator testable and separate from LangGraph node wiring; avoids growing `temporal.py` with LLM concerns.

## Implementation Phases (for `/speckit-tasks`)

### Phase 1 — Models & pairing core

- Add `MacroBindingProposal`, `BindingValidationResult`, `MacroBindingRecord` Pydantic models
- Implement `pairing.py` (YoY quarterly/annual, QoQ sequential, single anchors)
- Unit tests against AAPL fixture manifest

### Phase 2 — Validator & CLI handoff

- Implement `validator.py` per [macro-binding-validator.md](./contracts/macro-binding-validator.md)
- Change `bind_filings_for_query` / `corpus_pipeline` so empty CLI scope does **not** pass full snapshot as pre-bound
- Pre-bound path: validator record-only approve

### Phase 3 — LLM planner & macro_router

- `planner.py` + `configs/macro_phrases.yaml`
- Refactor `macro_router` to: plan → validate → set `filing_set` or fail
- `QueryService` scope error path (FR-010)
- Mock LLM fixtures

### Phase 4 — Trajectory & trace

- `log_macro_binding()` MLflow artifact
- Extend `build_macro_router_trace_payload` and trajectory builder
- Contract + integration tests

### Phase 5 — Evaluation slice

- Author `macro_binding.jsonl` (≥50 items, ≥80% `multi_filing_required`)
- `evaluation/metrics/macro_binding.py` + integration gate (70% SC-002)
- Document in README + quickstart

## Complexity Tracking

No constitution violations requiring justification.
