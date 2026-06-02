# Per-Item Graph Slice Contract (013)

**Scope**: Per-item agent evaluation in `ReproRunner` graph variants and flat-chunk (default: same slice). Bundle-level `materialize-relevance` continues to use **full composite** graph (012 unchanged).

## Index construction

At reproduction session start:

1. Read `bundle_root/manifest.json` → `corpus_bundle.issuer_snapshots[]` with `{ticker, snapshot_id}`.
2. For each issuer snapshot file, read `GraphManifest.filing_refs` → map `accession` → `(ticker, snapshot_id)`.
3. Optionally merge `sampling_manifest.json` accession aliases if present in bundle.

**Output**: `AccessionIndex.lookup(accession) -> IssuerSnapshotRef | None`

## Slice loading

```text
load_item_subgraph(bundle_root, accessions: list[str]) -> (slice_id, GraphSnapshot)
```

| Rule | Behavior |
|------|----------|
| Empty accessions | Raise `MissingBindingsError` with item context |
| Unknown accession | Raise `MissingAccessionsError(item_id, [accessions...])` |
| Single issuer | Load one `.graphml`, no merge overhead beyond wrapper |
| Multi issuer (2–4) | Load each required snapshot, `_merge_snapshots(slice_id, ...)` |
| >4 issuers | Fail fast (dataset governance cap; paper items ≤2 typical) |

## Query API wiring

For each benchmark item:

1. `accessions = item.expected_bindings.accessions` (required for paper-v1.0).
2. `(slice_id, slice) = load_item_subgraph(...)` with cache reuse.
3. `graph_api = InMemoryGraphQueryAPI(slice)`.
4. `QueryService(graph_api=graph_api, issuer_id=slice.issuer_id)`.
5. `QueryRequest.snapshot_id = slice_id`.
6. `pre_bound_filings` filtered from **slice** `manifest.filing_refs` (not composite).

**Progress log** (stdout):

```text
  [graph-full] 42/200 item_abc issuers=[AAPL] nodes=12450 filings=1
```

## Flat-chunk policy

`FlatChunkBaseline` MUST restrict chunk corpus to nodes reachable from slice snapshots (same accession filter). Embedding cache keys include slice id or accession set hash to avoid cross-item pollution.

## Failure modes

| Condition | Error |
|-----------|-------|
| No `expected_bindings` | `MissingBindingsError` |
| Accession not in index | `MissingAccessionsError` |
| Missing graph file on disk | `FileNotFoundError` with path (012 style) |

No fallback to full 20-issuer composite or default AAPL graph.

## Performance acceptance

Integration test on v1.0.0 subset: single-issuer item `node_count` ≤ standalone issuer snapshot `node_count` + small merge overhead.

Optional CI benchmark job: 10-item smoke median time ≥25% faster vs composite baseline (documented operator script if not in CI).
