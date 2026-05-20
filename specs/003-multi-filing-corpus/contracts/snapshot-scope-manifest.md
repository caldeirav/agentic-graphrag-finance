# Snapshot Scope Manifest Contract (003)

**Artifact name**: `binding_manifest.json` (MLflow + CLI output)

## Schema

```json
{
  "snapshot_id": "d7600d84-cd00-41c5-8504-13a0d8557fc1",
  "issuer_id": "AAPL",
  "stale_snapshot": true,
  "bound_filings": [
    {
      "accession": "0000320193-24-000123",
      "form_type": "10-K",
      "fiscal_period": {
        "fiscal_year": 2024,
        "fiscal_quarter": null,
        "label": "FY2024"
      },
      "filed_at": "2024-11-01"
    }
  ],
  "newer_available": [
    {
      "accession": "0000320193-25-000001",
      "form_type": "10-Q",
      "fiscal_period": {
        "fiscal_year": 2025,
        "fiscal_quarter": 1,
        "label": "FY2025-Q1"
      },
      "filed_at": "2025-01-31"
    }
  ],
  "excluded_from_binding": [],
  "resolution_notes": ["prior_quarter → FY2024-Q4 (fiscal)"]
}
```

## CLI rendering (human-readable)

After `ask` completes, emit:

```text
--- Snapshot scope ---
Snapshot version: d7600d84-...
Stale: yes (newer filings available on EDGAR)
Bound:
  - FY2024 (10-K) accession 0000320193-24-000123
Newer available (not in snapshot):
  - FY2025-Q1 (10-Q) accession 0000320193-25-000001
```

## MLflow

- Log params: `snapshot_id`, `issuer_id`, `stale_snapshot`, `bound_accessions` (comma-separated)
- Log artifact: full `binding_manifest.json`
- Parent run MUST remain correlatable to `TrajectoryRecord` (001 contract)

## Validation rules

- Every successful multi-period/comparison answer MUST include ≥1 `bound_filings` entry per resolved period (SC-004)
- `stale_snapshot: true` MUST include non-empty `newer_available` when EDGAR has strictly newer filings than snapshot max `filed_at`
- Missing comparison period: `bound_filings` incomplete + answer `status=INSUFFICIENT_EVIDENCE` (SC-005)
