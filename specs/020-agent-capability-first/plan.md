# Implementation Plan: Agent Capability-First Numeric Synthesis

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

## Summary

Replace live-path template chunk dumps and weak temporal binding on the XBRL numeric stratum with structured synthesis output, benchmark fiscal hints in macro planning, and an LLM-guided XBRL fact resolution skill. Gate deterministic `_try_synthesize_*` handlers to mock/CI. Freeze a 26-item cohort for fast iteration. Amend constitution (Principle VII) and add Cursor rule.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: LangGraph, LangChain, Pydantic, existing `create_chat_llm`  
**Storage**: Cohort JSON in `data/benchmarks/custom-judge/drafts/quality-v2.0.1/`  
**Testing**: pytest unit + regression under `tests/regression/failure_modes/`  
**Target Platform**: Local repro / cohort-debug  
**Constraints**: No new keyword handlers; USE_MOCK_LLM gates deterministic shortcuts

## Project Structure

### Documentation (this feature)

```text
specs/020-agent-capability-first/
├── spec.md
├── plan.md
├── tasks.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── structured-answer.schema.json
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
src/retrieval/
├── skills/
│   ├── structured_answer.py      # NEW: schema, parse, render, chunk-dump guard
│   └── xbrl_fact_resolution.py   # NEW: LLM fact picker
├── synthesis.py                  # MODIFY: live path, gate handlers
├── macro/planner.py              # MODIFY: temporal hints in prompt
└── orchestration/
    ├── state.py                  # MODIFY: fiscal_period_labels_json
    └── nodes/macro_router.py     # MODIFY: pass hints to planner

src/retrieval/service.py          # MODIFY: initial state fiscal hint
src/evaluation/reproduction/runner.py  # MODIFY: metadata fiscal_period_labels

data/benchmarks/custom-judge/drafts/quality-v2.0.1/
└── xbrl_numeric_cohort.json      # NEW: 26 item ids

.specify/memory/constitution.md   # MODIFY: Principle VII
.cursor/rules/
├── agent-capability-first.mdc    # NEW
└── specify-rules.mdc             # MODIFY: plan pointer
```

## Execution Order (matches spec user stories)

| Step | Deliverable | Key files |
|------|-------------|-----------|
| 1 | Structured answer contract + chunk-dump ban | `skills/structured_answer.py`, `synthesis.py` |
| 2 | Temporal binding in macro + metadata | `planner.py`, `macro_router.py`, `runner.py`, `service.py`, `state.py` |
| 3 | XBRL fact resolution skill | `skills/xbrl_fact_resolution.py`, `synthesis.py` |
| 4 | Cohort JSON + quickstart | `xbrl_numeric_cohort.json`, `quickstart.md`, regression test |
| 5 | Governance | `constitution.md`, `agent-capability-first.mdc`, `specify-rules.mdc` |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New `retrieval/skills/` package | Encapsulate LLM skills separate from orchestration nodes | Inline prompts in synthesis.py would violate separation and testability |
| Gate deterministic handlers to mock | Preserve CI fixtures without polluting live answers | Removing handlers breaks existing unit tests |

## Phase 0: Research

See [research.md](./research.md). Root cause confirmed: retrieval succeeds (MRR≈0.96) but synthesis emits template dumps and wrong-period numerics.

## Phase 1: Design

See [data-model.md](./data-model.md) and [contracts/structured-answer.schema.json](./contracts/structured-answer.schema.json).

## Phase 2: Implementation & Validation

Execute [tasks.md](./tasks.md) in order. Validate with:

```bash
uv run pytest tests/unit/test_structured_answer.py tests/unit/test_xbrl_fact_resolution.py tests/regression/failure_modes/test_no_template_dump_live.py -q
```

Cohort iteration:

```bash
uv run agent-query repro cohort-debug --manifest releases/paper-v1.1/manifest.yaml \
  --cohort data/benchmarks/custom-judge/drafts/quality-v2.0.1/xbrl_numeric_cohort.json
```

## Constitution Check

- Layer separation preserved: skills live in `retrieval/`, evaluation only passes metadata.
- Strong typing: Pydantic models for structured answer and resolution result.
- Evaluation modularity: cohort file is data-only; no retrieval imports in evaluation beyond runner metadata.

**Post-Phase-1**: Principle VII added; no constitution violations.
