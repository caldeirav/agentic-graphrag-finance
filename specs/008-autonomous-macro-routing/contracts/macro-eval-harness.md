# Macro Binding Evaluation Harness (008)

**Feature**: 008-autonomous-macro-routing | **Dataset**: `data/benchmarks/finagentbench/macro_binding.jsonl`

## Benchmark case schema

Extends [003 temporal-scope](../003-multi-filing-corpus/contracts/temporal-scope.md) case shape:

```json
{
  "item_id": "macro-aapl-yoy-revenue-q",
  "dataset": "finagentbench",
  "question": "How did revenue change year over year in the latest quarter?",
  "operation_class": "numeric",
  "multi_filing_required": true,
  "temporal_scope": {
    "anchor": null,
    "comparison_mode": null,
    "periods": [],
    "compare_periods": [],
    "accessions": []
  },
  "expected_bindings": {
    "accessions": ["0000320193-26-000006", "0000320193-25-000073"],
    "fiscal_periods": ["FY2026-Q1", "FY2025-Q1"]
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `multi_filing_required` | yes | For SC-001 harness classification |
| `expected_bindings.accessions` | yes | Exact set match for SC-002 |
| `temporal_scope` | yes | Empty fields = autonomous macro path in eval |

**Prohibited**: cases with only NL in `question` and no `expected_bindings`.

## Metrics

| Metric | Definition |
|--------|------------|
| `macro_binding_accuracy` | % items where selected accession set == `expected_bindings.accessions` (set equality) |
| `multi_filing_rate` | % items with `multi_filing_required=true` in slice |
| `macro_fail_closed_rate` | % items where validator failed when rubric expects fail |

## Gates (release)

| ID | Threshold |
|----|-----------|
| SC-001 | ≥ 80% of slice items have `multi_filing_required=true` |
| SC-002 | ≥ 70% `macro_binding_accuracy` on slice |
| SC-003 | 100% runs emit required `macro_binding` fields; verified by T029a batch (n≥50) or eval harness artifact audit |

## Runner integration

```bash
uv run agent-query test --macro-binding --ticker AAPL
# or
uv run pytest tests/integration/test_macro_binding_benchmark.py -q
```

Runner MUST:

1. Materialize or load fixture snapshot per issuer
2. Invoke ask graph with **empty** CLI temporal scope (autonomous path)
3. Read `macro_binding.json` or trajectory — not final answer text
4. Emit MLflow child run `macro-binding-eval-{timestamp}`

## Loader

`FinAgentBenchDataset.load_macro_binding_slice()` or dedicated `MacroBindingDataset` registered in `evaluation/registry.py`.
