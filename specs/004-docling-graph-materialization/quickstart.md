# Quickstart: Docling-Graph Materialization (004)

**Branch**: `004-docling-graph-materialization`

## Prerequisites

- Completed [003 quickstart](../003-multi-filing-corpus/quickstart.md) setup (EDGAR agent, LM Studio optional for ask)
- `uv sync --locked`
- Fixture or live cache under `data/raw/sec_downloads/`

## 1. Materialize corpus (docling-graph builder)

```bash
uv run agent-query materialize --ticker AAPL --force-refresh
```

Expected:

- Snapshot under `data/graphs/AAPL/{snapshot_id}.graphml`
- `index.json` updated
- `{snapshot_id}.reachability.json` with `audit_ready: true` when pass rate ≥ 95%

## 2. Run reachability audit only

```bash
uv run agent-query graph-audit --ticker AAPL --snapshot-id <uuid>
```

Inspect:

```bash
cat data/graphs/AAPL/<snapshot_id>.reachability.json | jq '.pass_rate, .audit_ready'
```

## 3. Verify structural path (Python)

```python
from pathlib import Path
from graph.store import load_snapshot
from graph.reachability import shortest_structural_path

snap = load_snapshot("AAPL", "<snapshot_id>", Path("data/graphs"))
path = shortest_structural_path(snap, "doc-0000320193-26-000006", "<fact-node-id>")
print(path.edge_types, path.hop_count)
```

## 4. Ask with bound quarter (003 + graph evidence)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --anchor prior-quarter \
  --query "What was revenue in the prior quarter?"
```

Check MLflow run for `reachability.json` and trajectory edge types on citations.

## 5. Parity check (migration window)

```bash
USE_FIXTURE_INGESTION=1 uv run pytest tests/integration/test_graph_builder_parity.py -q
```

Compares legacy vs docling-graph node counts on AAPL fixtures.

## 6. Thematic similarity (optional)

```bash
export USE_THEMATIC_GRAPH_LINKS=1
uv run agent-query materialize --ticker AAPL --force-refresh
```

Threshold in `configs/graph_similarity.yaml`. CI runs with thematic **disabled**.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `audit_ready: false` | Read `entries` failures in `.reachability.json`; fix mapper CONTAIN chain |
| Huge graph / slow build | Expected with no XBRL cap; reduce corpus filings, not silent drop |
| Filing excluded | See materialize job member `failure_reason` (fail-closed) |

## Next

- `/speckit-tasks` for implementation checklist
