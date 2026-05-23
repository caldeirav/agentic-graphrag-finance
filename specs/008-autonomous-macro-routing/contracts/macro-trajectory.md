# Macro Trajectory Contract (008)

**Feature**: 008-autonomous-macro-routing | **Artifacts**: MLflow + console trace

## Required fields (every ask run)

Persisted in **`macro_binding.json`** (MLflow artifact) and mirrored in **`TrajectoryRecord`** / console `macro_router` trace payload.

```json
{
  "binding_source": "cli_prebound | autonomous",
  "comparison_mode": "yoy | qoq | sequential | none",
  "selected_accessions": ["0000320193-26-000006"],
  "temporal_anchor_summary": "latest_quarter",
  "rationale": "human-readable explanation",
  "proposal_source": "llm | deterministic | cli",
  "validation_status": "approved | failed | narrowed",
  "failure_codes": [],
  "proposal": { },
  "validation": { }
}
```

## Pre-bound path

When CLI supplies resolved `CorpusTemporalScope`:

- `binding_source` = `cli_prebound`
- `macro_llm_skipped` = true (no accession pick)
- Validator still runs in **record-only** mode (status must be `approved` or fail ask)
- `rationale` MUST cite CLI scope fields

## Failed macro binding

- `QueryStatus` ≠ `SUCCESS` unless response text is explicit scope error (FR-010)
- `macro_binding.json` still logged
- No meso/micro evidence in trajectory

## Console trace (007 extension)

`build_macro_router_trace_payload` adds:

| Field | Description |
|-------|-------------|
| `binding_source` | |
| `validation_status` | |
| `selected_accessions` | |
| `comparison_mode` | |
| `failure_codes` | when failed |
| `proposal_summary` | truncated intent |

## Contract tests

- `tests/contract/test_macro_trajectory_schema.py` — required keys
- `tests/integration/test_ask_macro_trajectory.py` — MLflow artifact on mock ask
