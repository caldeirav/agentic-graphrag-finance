# Data Model: Multi-Filing Issuer Corpus (003)

**Date**: 2026-05-20 | **Extends**: `src/models/` (`ingestion`, `graph`, `filing`, new `corpus`)

## New entities (`src/models/corpus.py`)

### `FiscalPeriodLabel`

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_year` | int | e.g. 2024 |
| `fiscal_quarter` | int \| None | 1–4 for 10-Q; None for 10-K annual |
| `label` | str | Canonical string e.g. `FY2024-Q3` |

Derived from `FilingRef.period_end` + `form_type` ordering within issuer snapshot.

### `CorpusDefinition`

| Field | Type | Description |
|-------|------|-------------|
| `issuer_id` | str | Ticker or CIK key used in paths |
| `mode` | enum | `default_trailing` \| `explicit_accessions` \| `date_range` |
| `form_types` | list[str] | Default `["10-K","10-Q"]` |
| `max_filings` | int | Default 12; hard reject if exceeded |
| `trailing_10k` | int | Default 1 (default_trailing mode) |
| `trailing_10q` | int | Default 4 |
| `accessions` | list[str] | explicit mode |
| `period_start` / `period_end` | date \| None | date_range mode |

Validation: `len(resolved_members) > max_filings` → `CorpusCapExceededError` (no snapshot published).

### `CorpusMember`

| Field | Type | Description |
|-------|------|-------------|
| `resolution` | FilingResolution | From 002 |
| `fiscal_period` | FiscalPeriodLabel | |
| `cache_entry` | CacheEntry \| None | After fetch |
| `status` | enum | `pending` \| `included` \| `failed` \| `excluded` |
| `failure_reason` | str \| None | |

### `CorpusMaterializationJob`

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | UUID |
| `corpus_definition` | CorpusDefinition | Input |
| `members` | list[CorpusMember] | Per-filing outcomes |
| `snapshot_id` | str \| None | Set when graph build succeeds |
| `started_at` / `completed_at` | datetime | |

### `IssuerSnapshotIndex` (`data/graphs/{issuer}/index.json`)

| Field | Type | Description |
|-------|------|-------------|
| `issuer_id` | str | |
| `latest_snapshot_id` | str | Pointer for default reuse |
| `versions` | list[SnapshotIndexEntry] | Append-only registry |

### `SnapshotIndexEntry`

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | str | |
| `created_at` | datetime | |
| `filing_refs` | list[FilingRef] | Summary from GraphManifest |
| `corpus_definition_hash` | str | Detect definition changes |

### `TemporalScope` (request / benchmark)

| Field | Type | Description |
|-------|------|-------------|
| `anchor` | str \| None | e.g. `latest_annual`, `latest_quarter`, `prior_quarter` |
| `periods` | list[FiscalPeriodLabel] | Explicit fiscal targets |
| `comparison_mode` | ComparisonMode | From `models.enums` |
| `compare_periods` | list[FiscalPeriodLabel] | For two-period compares |
| `accessions` | list[str] | Optional explicit override |

Benchmarks: populated structurally. CLI: optional flags → this model; else NL resolution.

### `FilingBinding`

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | str | Active graph version |
| `bound_filings` | list[FilingRef] | Subset used for this query |
| `resolution_notes` | list[str] | Defaults applied, duplicate period decisions |
| `assumptions` | list[str] | NL disambiguation notes |

### `SnapshotScopeManifest` (output / MLflow artifact)

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | str | |
| `issuer_id` | str | |
| `bound_filings` | list[BoundFilingEntry] | period, form, filed_at, accession |
| `stale_snapshot` | bool | |
| `newer_available` | list[BoundFilingEntry] | Not in snapshot (FR-012a) |
| `excluded_from_binding` | list[str] | Reasons |

### `BoundFilingEntry`

| Field | Type | Description |
|-------|------|-------------|
| `accession` | str | |
| `form_type` | str | |
| `fiscal_period` | FiscalPeriodLabel | |
| `filed_at` | date | |

## Extended entities

### `CLIAskRequest` (extend `models/ingestion.py`)

| Field | Type | Description |
|-------|------|-------------|
| `temporal_scope` | TemporalScope \| None | Explicit CLI flags |
| `corpus_definition` | CorpusDefinition \| None | Override default trailing |
| `reuse_snapshot_id` | str \| None | Pin version; stale warn still applies |
| `force_corpus_refresh` | bool | Re-materialize default corpus |

### `CLIAskResult` (extend)

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_scope` | SnapshotScopeManifest | Required on success |
| `filings_used` | list[FilingResolution] | Populated from binding |

### `GraphManifest` (no schema break)

Continue using `filing_refs: list[FilingRef]`; optional future field `fiscal_period_labels` in sidecar only.

## State transitions

```text
CorpusDefinition validated
  → CorpusMaterializationJob (fetch each member via 002)
  → parse each → ParsedDocument[]
  → build_snapshot → save_snapshot + index.json append
  → GraphSnapshotVersion (immutable)

Query + TemporalScope
  → resolve against snapshot manifest
  → FilingBinding (subset)
  → if missing period: extend job → new snapshot_id
  → QueryService.answer(snapshot_id, metadata.binding_manifest)
```

## Relationships

```text
IssuerCorpus 1──* CorpusMember *──1 CacheEntry (002)
GraphSnapshotVersion 1──1 GraphManifest *──* FilingRef
FilingBinding *──1 GraphSnapshotVersion
BindingManifestRecord *──1 SnapshotScopeManifest (MLflow artifact)
```
