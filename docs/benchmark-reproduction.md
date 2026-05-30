# Benchmark Reproduction

> **Paper reproduction (custom-judge, five variants, table export):** see **[research-reproduction.md](research-reproduction.md)** (full walkthrough) and **[specs/012-research-repro-kit/quickstart.md](../specs/012-research-repro-kit/quickstart.md)** (operator quickstart for `paper-v1.0`).

Legacy single-suite benchmark notes:

1. **Frozen graph snapshot** — record `snapshot_id` and `issuer_id` under `data/graphs/`
2. **Dependency lock** — use `uv sync --locked` at the same commit SHA
3. **Judge config** — hash of `configs/judges/gemini_2_5_pro.yaml` and `GOOGLE_API_KEY` profile
4. **MLflow parent run** — note parent `run_id` from `reports/benchmark-*/summary.json`

```bash
USE_MOCK_LLM=0 USE_MOCK_JUDGE=0 uv run python -m evaluation.cli \
  --suite pilot \
  --snapshot-id <snapshot_id> \
  --issuer-id <cik> \
  --datasets finder,finagentbench,financebench \
  --max-items 100
```

Aggregate metrics in `reports/benchmark-<id>/summary.json` should match within floating-point tolerance when re-run with identical inputs.
