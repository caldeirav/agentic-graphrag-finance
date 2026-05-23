# Quickstart: Graph-Native Meso and Micro Navigation (009)

**Branch**: `009-graph-native-meso-micro` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Merged **004** (graph materialization), **008** (macro binding), **007** (console trace)
- Materialized snapshot: `uv run agent-query materialize --ticker AAPL`
- LM Studio or `USE_MOCK_LLM=1` for CI

## 1. Multi-hop narrative (footnote chain)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --trace verbose \
  --query "What critical accounting estimates are described in the footnotes to the financial statements?"
```

Expect **stderr** meso/micro panels:

- `navigation_mode=graph_native`
- `edge_types_used` includes `CONTAINS`, `FOOTNOTE_OF` and/or `REFERENCES`
- `sample_path` showing section → table/paragraph → footnote hops

Inspect MLflow artifact **`navigation_trace.json`** for full `visits[]` with edge types.

## 2. XBRL numeric via graph path

```bash
uv run agent-query ask \
  --ticker AAPL \
  --trace normal \
  --query "What was revenue in the prior quarter?"
```

Expect macro autonomous binding (008) then micro path ending at `CHUNK_XBRL_FACT` with structural hops only (no semantic edges).

## 3. Year-over-year (multi-filing meso)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --trace normal \
  --query "How did revenue change year over year?"
```

Expect meso ranks sections **per filing** (two document roots); top 3 sections each; no `TEMPORAL_TRANSITION` in `structural_edge_types_used`.

## 4. Insufficient evidence (no heuristic fallback)

Use a query that does not map to materialized sections/chunks on a thin fixture, or exhaust budget in test harness.

Expect `INSUFFICIENT_EVIDENCE` with partial `navigation_trace` — **no** flat keyword chunk pool in trajectory.

## 5. Gold-path benchmark (CI)

```bash
USE_MOCK_LLM=1 uv run agent-query test --gold-path --ticker AAPL
```

Expect exit 0 when `chunk_reach_rate >= 0.75` on fixture JSONL.

## 6. Contract tests

```bash
USE_MOCK_LLM=1 uv run pytest \
  tests/unit/test_navigation_validator.py \
  tests/contract/test_navigation_trajectory_schema.py \
  tests/integration/test_gold_path_benchmark.py -q
```

## Trajectory fields checklist (SC-002)

For five manual queries, confirm from console + `navigation_trace.json` alone:

1. Sections ranked per filing
2. Edge type per hop
3. Chunks used in answer linked to `micro_paths`
4. Rejected proposals (if any) with codes
5. `scan_ratio` below 0.90 on gold-path items
