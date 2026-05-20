# Contract: Reachability Audit

**Feature**: 004-docling-graph-materialization | **Artifact**: `{snapshot_id}.reachability.json`

## Trigger

- Automatically after `agent-query materialize` when `run_audit=true` (default)
- Manual: `uv run agent-query graph-audit --ticker AAPL --snapshot-id <uuid>`

## Sample design

| Rule | Value |
|------|-------|
| Minimum sample size | 100 |
| Stratification | By `form_type` (10-K / 10-Q) proportional to snapshot; by `node_kind` (≥60% XBRL fact, ≤40% table row) |
| Random seed | Fixed in config for reproducibility (`configs/graph_audit.yaml`) |
| Population | All `CHUNK_XBRL_FACT` and table `CHUNK_ROW` nodes with numeric cell content in pilot snapshot |

## Path rules

- Start: `doc-{accession}` for fact’s filing
- End: target evidence `node_id`
- Allowed edges: `CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES` (see [edge-catalog.md](./edge-catalog.md))
- Max hops: **6**
- Algorithm: BFS shortest path; first path wins

## Pass criteria

```text
pass_rate = count(reachable) / sample_size
audit_ready = pass_rate >= 0.95
```

## JSON schema (informal)

```json
{
  "snapshot_id": "uuid",
  "issuer_id": "AAPL",
  "hop_budget": 6,
  "sample_size": 120,
  "pass_rate": 0.97,
  "pass_threshold": 0.95,
  "audit_ready": true,
  "structural_edge_types": ["CONTAINS", "NEXT", "FOOTNOTE_OF", "REFERENCES"],
  "entries": [
    {
      "node_id": "doc-...-xbrl-abc",
      "accession": "0000320193-26-000006",
      "node_kind": "xbrl_fact",
      "reachable": true,
      "hop_count": 3,
      "path_edge_types": ["CONTAINS", "CONTAINS", "CONTAINS"],
      "path_node_ids": ["doc-...", "doc-...-xbrl-facts", "doc-...-xbrl-abc"]
    }
  ],
  "created_at": "2026-05-21T00:00:00Z",
  "builder_version": "docling-graph-mapper-1.0.0"
}
```

## MLflow

- Log artifact `reachability.json` on materialize run when audit executes
- Tags: `audit_ready`, `audit_pass_rate`, `hop_budget`

## Consumer obligations

- Retrieval MUST NOT cite nodes with `reachable=false` in latest audit for same snapshot version
- Benchmarks MAY assert `audit_ready=true` for graph-dependent cases
