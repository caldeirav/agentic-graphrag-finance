# Ingestion → Parsing Boundary Contract

## ingestion public API

```python
def resolve_identifier(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
) -> FilingResolution: ...

def fetch_filing(
    resolution: FilingResolution | None = None,
    *,
    ticker: str | None = None,
    form_type: str = "10-K",
    latest: bool = True,
    force_refresh: bool = False,
) -> CacheEntry: ...
```

## Handoff to parsing

**Input**: `CacheEntry.local_path` containing:
- `manifest.json` (`XBRLArtifactManifest`)
- Raw `.xml` / `.xsd` files

**Parsing entry**:
```python
def parse_sec_download(
    cache_entry: CacheEntry,
    *,
    config_path: Path | None = None,
) -> ParsedDocument: ...
```

Located in `parsing/sec_download_adapter.py` (new thin adapter).

## Rules

- `ingestion/` MUST NOT import `graph`, `retrieval`, `evaluation`, or `tracing`
- `parsing/` MAY import `ingestion` types (`CacheEntry`, `FilingResolution`) only
- `cli/` MAY import all layer public facades; MUST NOT import `retrieval.orchestration.nodes`
