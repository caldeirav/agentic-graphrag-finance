# Reproduction Report CLI Contract (014)

**Extends**: `agent-query repro` command group from feature 012/013.

## New subcommand

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

## Flags

| Flag | Required | Default | Notes |
|------|----------|---------|-------|
| `--input` | yes | — | Existing repro output directory |
| `--output` | no | `<input>/report.html` | HTML output path |
| `--format` | no | `html` | `html` or `latex-only` |
| `--table` | no | all paper tables | Repeatable: `headline`, `by_profile`, `variant_delta`, `trajectory_audit` |
| `--max-item-rows` | no | project default | Soft cap for drill-down rendering |
| `--manifest` | no | auto-discover | Optional release manifest path for provenance |
| `--delta-threshold` | no | project default | Highlight threshold vs `graph-full` |

## Behavior

1. Validate required report inputs under `--input`.
2. Load optional files when present.
3. Render:
   - Run summary
   - Paper table section
   - Variant comparison
   - Item drill-down (when variant `results.json` exists)
4. Emit report artifact or LaTeX-only payload.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Required input missing/invalid |
| `3` | Output write failure |

## Non-goals enforced

- No calls to generation/judge/retrieval paths
- No network access required after command starts
- No mutation of source repro artifacts

