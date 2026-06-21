# Contract: Failure-Mode Regression Suite

**Feature**: 019 | **Path**: `tests/regression/failure_modes/`

## Purpose

Each agent remediation cluster MUST register at least one regression case that:

- **Fails** on pre-fix behavior (or pinned baseline commit fixture)
- **Passes** after remediation is applied
- Does **not** regress unrelated golden cases in `tests/unit/test_synthesis_*.py`

## Clusters

| ID | Cluster | Fixture file | Asserts |
|----|---------|--------------|---------|
| FM-M1 | Macro binding | `macro_10q_vs_10k.json` | Correct form type in filing_set |
| FM-M2 | Numeric XBRL | `numeric_xbrl_revenue.json` | Deterministic numeric answer, not template dump |
| FM-M3 | Template guard | `xbrl_ranked_no_template.json` | synthesis_path != template when XBRL ranked |
| FM-M4 | Comparison (stretch) | `comparison_contrast.json` | Answer contains cross-filing contrast |

## CI integration

```bash
uv run pytest tests/regression/failure_modes -q
```

`cohort_gate_thresholds.require_regression_suite_pass: true` checks this suite passed before `run-all`.

## Fixture format

```json
{
  "item_id": "fixture-m2-001",
  "query": "...",
  "evidence_chunks": [...],
  "filing_set": [...],
  "macro_plan": {...},
  "expect": {
    "synthesis_path": "numeric_xbrl_deterministic",
    "answer_contains": ["416.16"],
    "answer_excludes": ["Based on"]
  }
}
```

## Non-goals

- Not a replacement for full repro or cohort validate
- Does not use live EDGAR or LLM in CI (mock/fixture ingestion)
