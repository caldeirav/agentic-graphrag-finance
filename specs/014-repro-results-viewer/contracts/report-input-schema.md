# Reproduction Report Input Contract (014)

## Required files

```text
<input>/
├── repro_run.json
├── tables/
│   ├── headline.csv
│   ├── by_profile.csv
│   ├── variant_delta.csv
│   └── trajectory_audit.csv
└── <variant>/results.json   # required for full drill-down; partial reports allowed
```

## Optional files

| Path | Use |
|------|-----|
| `tables/headline.tex` | Existing TeX fallback/compare |
| `export_manifest.json` | Export metadata display |
| `releases/*/manifest.yaml` | Provenance block (pins, release context) |

## Field expectations

### `repro_run.json`

- `release_tag` (required)
- `repro_run_id` (required)
- timestamps (`started_at`, `completed_at`) for duration
- `variant_runs[]` including variant identifiers and optional MLflow parent ids

### `tables/*.csv`

Must follow 012 paper-table-export contract:
- `headline.csv`
- `by_profile.csv`
- `variant_delta.csv`
- `trajectory_audit.csv`

### `{variant}/results.json`

Rows must be parseable as benchmark result records including:
- `item_id`
- `judge_status`
- score fields (`outcome_score`, rubric/structural metrics when available)
- `validation_status`
- optional answer/citations and trajectory references

## Validation rules

1. Missing required files -> hard error with absolute path in message.
2. Missing optional files -> warning surfaced in report summary.
3. Unknown variants in results directories -> include as extra variants without failing.
4. CSV header mismatch against contract -> hard error with offending file and column list.
5. Missing `{variant}/results.json` -> warning and incomplete variant in summary; do not abort (research R7). Drill-down renders only for variants with checkpoints.

