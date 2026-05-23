# Quickstart: Autonomous Macro Routing (008)

**Branch**: `008-autonomous-macro-routing` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Merged **003** (multi-filing corpus), **007** (console trace)
- Materialized issuer snapshot: `uv run agent-query materialize --ticker AAPL`
- LM Studio or `USE_MOCK_LLM=1` for deterministic CI

## 1. Natural-language quarter (autonomous macro)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --trace normal \
  --query "What was revenue in the prior quarter?"
```

Expect **stderr** macro panel:

- `binding_source=autonomous`
- `validation_status=approved`
- One 10-Q accession (second-latest by period end)

## 2. Year-over-year comparison

```bash
uv run agent-query ask \
  --ticker AAPL \
  --trace normal \
  --query "How did revenue change year over year?"
```

Expect two accessions (latest 10-Q + same fiscal quarter prior year, or latest two 10-Ks if annual framing).

## 3. Explicit CLI scope (pre-bound)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --period FY2026-Q1 \
  --trace normal \
  --query "What was revenue for that quarter?"
```

Expect `binding_source=cli_prebound`, `macro_llm_skipped=true`.

## 4. Fail closed (missing history)

On a sparse fixture corpus, ask for prior quarter with only one 10-Q:

Expect `validation_status=failed`, scope error message, no fabricated revenue.

## 5. Inspect MLflow macro artifact

After ask, open run artifacts → **`macro_binding.json`** — verify `selected_accessions`, `comparison_mode`, `rationale`.

## 6. Macro binding benchmark

```bash
uv run pytest tests/integration/test_macro_binding_benchmark.py -q
```

Or (when CLI wired):

```bash
uv run agent-query test --macro-binding --ticker AAPL
```

## 7. Unit tests (validator only)

```bash
uv run pytest tests/unit/test_macro_validator.py -q
```

No LLM required — stub proposals against fixture manifests.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Full corpus used | Empty CLI scope still passing all filings — verify 008 corpus_pipeline handoff |
| Macro skipped | `--period` / `--anchor` set → pre-bound path |
| Wrong YoY pair | `macro_binding.json` `comparison_mode` and validator `failure_codes` |
| Benchmark < 70% | `data/benchmarks/finagentbench/macro_binding.jsonl` labels vs manifest |
