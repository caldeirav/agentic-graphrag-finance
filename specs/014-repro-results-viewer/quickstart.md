# Quickstart: Research Reproduction Results Viewer (014)

**Feature**: 014-repro-results-viewer | **Date**: 2026-06-02

## Prerequisites

- A completed reproduction output directory from 012/013 (`reports/repro-{tag}/`)
- Exported paper tables under `tables/`
- Optional: release manifest path for provenance details

## Generate the HTML report

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

Open `reports/repro-paper-v1.0/report.html` in a browser.

## Generate report from smoke output

```bash
uv run agent-query repro report \
  --input reports/repro-paper-smoke \
  --output reports/repro-paper-smoke/report.html
```

## LaTeX-only copy pipeline

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --format latex-only \
  --table headline > /tmp/headline.tex
```

## Useful options

| Option | Purpose |
|--------|---------|
| `--table headline --table variant_delta` | Restrict output/copy scope |
| `--manifest releases/paper-v1.0/manifest.yaml` | Add release provenance block |
| `--delta-threshold 0.10` | Highlight larger gaps vs `graph-full` |
| `--max-item-rows 500` | Limit rendered drill-down rows |

## CI smoke expectation

Report generation must succeed offline on fixture or `paper-smoke` outputs:

```bash
uv run pytest tests/integration/test_repro_report_smoke.py -q
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| Missing `repro_run.json` | Verify `--input` points to repro root, not `tables/` |
| Missing `tables/*.csv` | Run `repro export-tables` first |
| Empty drill-down section | Confirm `{variant}/results.json` exists and is valid JSON |
| Browser appears blank offline | Ensure output is self-contained and assets path is local |

