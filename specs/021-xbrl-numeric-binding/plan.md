# Implementation Plan: FY Binding, Concept-Aware XBRL, and Numeric Computation

**Branch**: `019-agent-failure-investigation` | **Date**: 2026-06-23 | **Spec**: [spec.md](./spec.md)

## Summary

Close the gap between high MRR and zero value_alignment on the 26-item XBRL cohort by (1) deterministic FY 10-K binding, (2) structured XBRL fact catalog + concept-aware resolution, (3) Python-backed metric computation, and (4) removing live deterministic numeric overrides. Builds on 020 structured synthesis.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: existing macro/pairing/validator, `parsing/xbrl_facts.py`, 020 skills  
**Testing**: unit fixtures + cohort-debug on `xbrl_numeric_cohort.json`  
**Constraints**: Principle VII—skills + schemas; deterministic math OK; no new `_try_synthesize_*` live handlers

## Project Structure

```text
specs/021-xbrl-numeric-binding/
├── spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md
├── contracts/
│   ├── temporal-scope-intent.schema.json
│   ├── metric-intent.schema.json
│   └── structured-answer-v2.schema.json
└── checklists/requirements.md

src/retrieval/skills/
├── temporal_scope.py          # NEW step 1
├── xbrl_fact_catalog.py       # NEW step 2
├── metric_intent.py           # NEW step 3
├── numeric_computation.py     # NEW step 3
├── xbrl_fact_resolution.py    # MODIFY step 2
└── structured_answer.py       # MODIFY step 3

src/retrieval/macro/
├── pairing.py                 # MODIFY step 1 (annual vs quarterly cue)
├── validator.py               # MODIFY step 1 (period mismatch guard)
└── planner.py                 # MODIFY step 1 (period_labels in proposal)

src/retrieval/orchestration/nodes/macro_router.py  # MODIFY step 1
src/retrieval/synthesis.py     # MODIFY steps 3–4 (wire pipeline, gate overrides)

tests/
├── unit/test_temporal_scope.py
├── unit/test_xbrl_fact_catalog.py
├── unit/test_metric_intent.py
├── unit/test_numeric_computation.py
└── regression/failure_modes/test_live_no_deterministic_numeric.py
```

## Execution Order (steps 1–4)

| Step | User story | Deliverable | Gate |
|------|------------|-------------|------|
| **1** | US1 FY binding | `temporal_scope.py`, pairing/validator/macro_router | FY2025 questions bind 10-K |
| **2** | US2 Concept catalog | `xbrl_fact_catalog.py`, enhance resolution | Wrong-concept rate ↓ on 0436/0536 |
| **3** | US3 Computation | `metric_intent.py`, `numeric_computation.py`, schema v2 | delta/ratio items produce numbers |
| **4** | US4 Gate overrides | `synthesis.py` live path | No deterministic numeric injection |

**Integration point**: `synthesize()` live path becomes:

```text
temporal intent (state) → [macro already bound]
→ build fact catalog → classify metric intent
→ resolve facts → compute (if needed) → structured answer → render
```

## Phase 0: Research

See [research.md](./research.md). Confirmed: 020 reduced template dumps; VA=0 due to binding + concept + computation gaps.

## Phase 1: Design

See [data-model.md](./data-model.md) and `contracts/`.

## Phase 2: Validation

```bash
export OFFLINE_BENCHMARK=1
uv run pytest tests/unit/test_temporal_scope.py \
  tests/unit/test_xbrl_fact_catalog.py \
  tests/unit/test_metric_intent.py \
  tests/unit/test_numeric_computation.py \
  tests/regression/failure_modes/test_live_no_deterministic_numeric.py -q

uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-xbrl-021-debug \
  --no-resume
```

Success: SC-001 through SC-004 in spec.md.

## Complexity Tracking

| Violation | Why Needed | Rejected Alternative |
|-----------|------------|----------------------|
| Validator period override | Prompt-only hints failed on cohort | More planner prompt text |
| Python computation | LLM arithmetic unreliable on financebench | LLM-only ratio answers |
| Pre-filter with `xbrl_concept_matches_query` | Reduces LLM pick of wrong concept | LLM-only resolution (020 insufficient) |

## Constitution Check

- Skills live in `retrieval/skills/`; evaluation passes metadata only.
- Strong typing via Pydantic models + JSON schemas.
- Principle VII: no live keyword synthesis handlers; mock/CI gates preserved.

**Status**: PASS (pre-implementation).
