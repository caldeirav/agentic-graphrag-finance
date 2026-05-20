# Corpus Orchestration Boundary (003)

**Extends**: [002 ingestion-boundary](../../002-live-disclosure-cli/contracts/ingestion-boundary.md)

## ingestion public API (additive)

```python
def list_recent_filings(
    *,
    cik: str | None = None,
    ticker: str | None = None,
    form_types: list[str] | None = None,
    max_per_form: int = 6,
) -> list[FilingResolution]: ...

def materialize_corpus(
    definition: CorpusDefinition,
    *,
    force_refresh: bool = False,
) -> CorpusMaterializationJob: ...
```

## Rules

- `materialize_corpus` MUST call existing `fetch_filing` per resolved accession (no duplicate download logic)
- `materialize_corpus` MUST NOT import `graph`, `retrieval`, `evaluation`, or `tracing`
- On `CorpusCapExceededError`, MUST NOT write graph artifacts or `index.json` entries

## graph public API (additive)

```python
def build_issuer_snapshot(
    issuer_id: str,
    parsed_docs: list[ParsedDocument],
    *,
    snapshot_id: str | None = None,
    base_dir: Path = Path("data/graphs"),
) -> GraphSnapshot: ...

def register_snapshot(snapshot: GraphSnapshot, base_dir: Path) -> None: ...

def get_latest_snapshot(issuer_id: str, base_dir: Path) -> GraphSnapshot | None: ...

def probe_stale_filings(
    issuer_id: str,
    snapshot: GraphSnapshot,
) -> list[FilingResolution]: ...
```

## cli orchestration

```python
def run_materialize_pipeline(definition: CorpusDefinition) -> CorpusMaterializationJob: ...

def run_ask_pipeline(request: CLIAskRequest) -> CLIAskResult: ...
```

- `run_ask_pipeline` MUST: resolve/load snapshot → `bind_filings_for_query` → `QueryService.answer`
- `cli/` MAY import `ingestion.corpus`, `graph.registry`, `retrieval.temporal`, `retrieval.service`
- `cli/` MUST NOT import `retrieval.orchestration.nodes` directly

## parsing handoff (per filing)

Unchanged 002 contract: `CacheEntry` → `parse_from_cache` → `ParsedDocument`.

**New convention**: persist parsed JSON as `data/parsed/{ticker}/{accession}.json` (one file per filing) so multi-filing builds do not overwrite a single issuer file.
