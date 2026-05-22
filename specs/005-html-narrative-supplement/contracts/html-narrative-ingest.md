# Contract: Supplementary HTML Narrative Ingest

**Feature**: 005-html-narrative-supplement

## Preconditions

| Rule | Enforcement |
|------|-------------|
| Cached XBRL package **complete** for accession | `validators` / manifest instance + schema present |
| No orphan HTML-only cache | Reject ingest if XBRL missing (FR-001) |

## Resolution order

1. **Inline/iXBRL** in package: largest suitable HTML-bearing file (`*_htm.xml` text or companion `.htm` in same directory post-unzip).
2. **Fallback**: EDGAR `index.json` → primary document `.htm` (not exhibit) via existing `edgar_client` / `edgar_xbrl` HTTP helpers.

Record `html_artifact_role` and `html_artifact_relpath` on manifest.

## Public API (ingestion layer)

```python
# src/ingestion/html_narrative.py

def resolve_narrative_html(cache_root: Path, entry: CacheEntry) -> SupplementaryHtmlResolution: ...

def ingest_html_narrative(
    resolution: FilingResolution,
    *,
    cache_root: Path,
    force_refresh: bool = False,
) -> CacheEntry: ...
```

## Status semantics (FR-011)

| Status | Meaning |
|--------|---------|
| `success` | HTML artifact stored and readable |
| `failed` | Download/resolve failed; XBRL cache untouched |
| `skipped` | `--skip-html-narrative` or operator opt-out |
| `not_attempted` | XBRL ingest incomplete |

## Forbidden

- HTML ingest without XBRL package
- Deleting XBRL instance files on HTML-only refresh
- Replacing XBRL manifest roles with HTML-only entry

## Integration point

`fetch_filing` or `corpus_pipeline` calls `ingest_html_narrative` **after** successful XBRL fetch when HTML narrative not skipped.
