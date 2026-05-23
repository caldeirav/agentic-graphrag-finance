# Macro Planner LLM Contract (008)

**Feature**: 008-autonomous-macro-routing | **Module**: `src/retrieval/macro/planner.py`

## Responsibility

Produce **`MacroBindingProposal`** JSON from query + manifest summary. Does **not** finalize `filing_set`.

## Prompt inputs

| Input | Max size |
|-------|----------|
| User query | full |
| Filing manifest summary | accession, form_type, period_end, fiscal_label per ref (≤ 20 refs) |
| Phrase catalog excerpt | from `configs/macro_phrases.yaml` |

## Required JSON shape

```json
{
  "intent_summary": "string",
  "comparison_mode": "none | yoy | qoq | sequential",
  "anchor": "latest_quarter | prior_quarter | latest_annual | null",
  "period_labels": ["FY2025-Q1"],
  "proposed_accessions": [],
  "is_comparison": false,
  "quarterly_metric_cue": false
}
```

## Mock / CI

When `USE_MOCK_LLM=1`, return fixture proposal from query hash or `tests/fixtures/macro_planner/` — still passes through validator.

## Tracing

Uses `traced_llm_invoke("macro_router", ...)` — 007 trace unchanged stage id.

## Errors

Malformed JSON → treat as empty proposal → validator fails with `invalid_proposal` (fail closed).
