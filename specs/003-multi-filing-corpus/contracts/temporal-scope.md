# Temporal Scope Contract (003)

## Benchmark case schema (required)

Each multi-period benchmark case MUST include:

```json
{
  "case_id": "aapl-prior-quarter-revenue",
  "issuer": { "ticker": "AAPL" },
  "query": "What was revenue in the prior quarter?",
  "temporal_scope": {
    "anchor": "prior_quarter",
    "comparison_mode": null,
    "periods": [],
    "compare_periods": [],
    "accessions": []
  },
  "expected_bindings": {
    "accessions": ["0000320193-24-000076"],
    "fiscal_periods": ["FY2024-Q4"]
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `temporal_scope` | **Yes** | Omit → runner fails at setup (FR-009a) |
| `expected_bindings.accessions` | **Yes** for binding tests | Expert labels for SC-003 |
| `expected_bindings.fiscal_periods` | Recommended | Fiscal labels only (clarification A) |

**Prohibited**: benchmark cases that rely solely on NL in `query` for temporal selection.

## CLI flags → `TemporalScope`

| Flag | Maps to |
|------|---------|
| `--period FY2024-Q3` | `periods: [{label: "FY2024-Q3", ...}]` |
| `--anchor prior-quarter` | `anchor: "prior_quarter"` |
| `--compare FY2024-Q3,FY2024-Q2` | `compare_periods: [...]` |
| `--accession` (repeatable) | `accessions: [...]` |

Precedence (FR-009b/c):
1. Explicit CLI `TemporalScope` fields override NL-derived bindings when reconcilable
2. Irreconcilable NL vs flags → validation error before retrieval

## Resolution algorithm (deterministic core)

Given `snapshot.manifest.filing_refs` sorted by `period_end`:

| Anchor | Selection |
|--------|-----------|
| `latest_annual` | Latest `form_type == 10-K` |
| `latest_quarter` | Latest `10-Q` by `period_end` |
| `prior_quarter` | Second-latest `10-Q` |
| Named `FYxxxx-Qn` | Match fiscal label derived from `period_end` |

Comparison sets resolve to ≥2 distinct accessions or fail closed (FR-011).

## Integration with LangGraph

When `FilingBinding` is computed in `cli/corpus_pipeline` before invoke:

```python
initial_state = {
    "query": request.query,
    "snapshot_id": binding.snapshot_id,
    "filing_set": binding.bound_filings,  # pre-bound
    "binding_manifest": scope_manifest.model_dump(),
}
```

`macro_router` MUST use pre-bound `filing_set` when present (skip LLM filing selection).
