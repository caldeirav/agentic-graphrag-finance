# Data Model: Live Disclosure Ingestion & Developer CLI

**Date**: 2026-05-18 | **Extends**: `001` models in `src/models/`

## New / Extended Entities

### `IssuerIdentifierInput` (CLI + ingestion)

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | str \| None | Stock symbol |
| `cik` | str \| None | SEC CIK |
| `accession` | str \| None | EDGAR accession |

Validation: exactly one primary resolver path; conflict if ticker-implied CIK ≠ provided CIK.

### `FilingResolution` (ingestion)

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | str | Canonical ticker used in paths |
| `cik` | str | Resolved CIK |
| `accession` | str | EDGAR accession |
| `form_type` | str | 10-K, 10-Q, etc. |
| `filed_at` | date | Filing date |
| `period_end` | date | Reporting period end |
| `sec_api_filing_url` | str | Source URL from sec-api |

### `XBRLArtifact` (ingestion)

| Field | Type | Description |
|-------|------|-------------|
| `filename` | str | Base name |
| `role` | enum | instance \| schema \| calculation \| label \| presentation \| other |
| `url` | str | Download URL |
| `content_hash` | str \| None | SHA-256 after download |

### `XBRLArtifactManifest`

| Field | Type | Description |
|-------|------|-------------|
| `resolution` | FilingResolution | Parent filing |
| `artifacts` | list[XBRLArtifact] | Files to fetch |
| `complete` | bool | Validation passed |

### `CacheEntry` (ingestion)

| Field | Type | Description |
|-------|------|-------------|
| `local_path` | Path | `data/raw/sec_downloads/{ticker}/{accession}/` |
| `manifest_path` | Path | `{local_path}/manifest.json` |
| `content_hash` | str | Aggregate package hash |
| `parse_ready` | bool | Passed validators |
| `cached_at` | datetime | UTC timestamp |
| `cache_hit` | bool | True if skipped download |

### `FetchJob`

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | UUID |
| `status` | enum | pending \| downloading \| validating \| complete \| failed |
| `error` | str \| None | Failure detail |
| `resolution` | FilingResolution \| None | |

### `CLIAskRequest`

| Field | Type | Description |
|-------|------|-------------|
| `identifier` | IssuerIdentifierInput | |
| `query` | str | Natural language question |
| `form_types` | list[str] | Default `["10-K","10-Q"]` |
| `force_refresh` | bool | Bypass cache |
| `snapshot_id` | str \| None | Reuse graph if set |

### `CLIAskResult`

| Field | Type | Description |
|-------|------|-------------|
| `answer_text` | str | Grounded response |
| `citations` | list[EvidenceChunk] | From `001` |
| `status` | QueryStatus | |
| `mlflow_run_id` | str | |
| `snapshot_id` | str | Graph used |
| `filings_used` | list[FilingResolution] | |
| `timings_ms` | dict[str, int] | Per-stage durations |

### `CLITestResult`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | |
| `node_counts` | dict[str, int] | By node type |
| `cache_entry` | CacheEntry | |
| `messages` | list[str] | Assertions |

## State: Cache Entry Lifecycle

```text
[Fetch requested]
  → resolve identifier (sec-api)
  → cache lookup by (ticker, accession) hash
      → HIT (parse_ready) → return CacheEntry
      → MISS → download artifacts → validate → atomic write → parse_ready
[Handoff to parsing]
  → ParsedDocument from instance XML / filing bundle
```

## Settings (`ingestion/settings.py`)

| Field | Env var | Default |
|-------|---------|---------|
| `sec_api_key` | `SEC_API_KEY` | required |
| `requests_per_second` | `SEC_API_REQUESTS_PER_SECOND` | 2 |
| `downloads_root` | `SEC_DOWNLOADS_ROOT` | `data/raw/sec_downloads` |
