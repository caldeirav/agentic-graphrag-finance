# Contract: Graph Materialization Boundary

**Feature**: 004-docling-graph-materialization

## Allowed inputs

| Source | Type | Path |
|--------|------|------|
| Parsed filing | `ParsedDocument` | `data/parsed/{ticker}/{accession}.json` |
| Corpus job | `list[ParsedDocument]` + `CorpusDefinition` | via `graph.registry.build_issuer_snapshot` |

## Forbidden in graph layer

- Raw EDGAR download (`data/raw/`)
- `fetch_filing`, `ingestion.corpus` network calls
- Docling parse re-run (belongs in `parsing/`)
- LangGraph / `QueryService` / LLM calls
- Benchmark judge models

## Public API (post-004)

```python
# src/graph/builder.py (facade)
def build_snapshot(
    issuer_id: str,
    documents: list[ParsedDocument],
    *,
    snapshot_id: str | None = None,
    similarity_config: SimilarityConfig | None = None,
) -> GraphSnapshot: ...

# src/graph/registry.py
def build_issuer_snapshot(
    issuer_id: str,
    docs: list[ParsedDocument],
    *,
    base_dir: Path,
    corpus_definition: CorpusDefinition | None = None,
    run_audit: bool = True,
) -> GraphSnapshot: ...

# src/graph/reachability.py
def audit_snapshot_reachability(
    snapshot: GraphSnapshot,
    *,
    hop_budget: int = 6,
    sample_size: int = 100,
    pass_threshold: float = 0.95,
) -> ReachabilityAuditReport: ...
```

## Fail-closed rules

| Condition | Action |
|-----------|--------|
| Document with zero sections | Exclude filing; `FilingMaterializationResult.status=failed` |
| Evidence node without CONTAIN path to `doc-{accession}` | Exclude filing |
| Unresolved footnote / external cross-ref | Record count; do not create traversable edge |
| Audit `pass_rate < 0.95` | `audit_ready=false` on manifest; ask MAY proceed with warning (003 stale pattern) |

## Output artifacts

- `{snapshot_id}.graphml` — unchanged schema via `graph.store`
- `{snapshot_id}.manifest.json` — extended audit fields
- `{snapshot_id}.reachability.json` — new

## Versioning

- `graph_builder_version` MUST bump when edge catalog or mapper semantics change
- Snapshot immutability: new version on any graph semantics change (003 FR-006)
