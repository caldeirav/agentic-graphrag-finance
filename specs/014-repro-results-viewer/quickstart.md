# Quickstart: Research Reproduction Results Viewer (014)

**Feature**: 014-repro-results-viewer | **Date**: 2026-06-02

## Prerequisites

- A completed reproduction output directory from 012/013/017 (`reports/repro-{tag}/`)
- Exported paper tables under `tables/`
- Optional: release manifest path for provenance and question/expected-answer enrichment

## Generate the HTML report

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v2.0-lock \
  --manifest releases/paper-v2.0/manifest.yaml \
  --output reports/repro-paper-v2.0-lock/report.html
```

Open `report.html` in a browser.

## Report sections (current layout)

| Section | Purpose |
|---------|---------|
| Run summary | Release tag, duration, variant exclusion counts, MLflow links |
| By evidence source | `variant_id` × `primary_evidence_source` rows; all exported metrics as columns |
| Variant comparison | Headline metrics pivoted (baseline `graph-full`) |
| Investigation notes | Aggregated anomaly checks (≤25 per run) |
| Paper tables | Headline + trajectory audit with LaTeX/CSV/Markdown copy buttons |
| Item drill-down | One row per benchmark item; variant columns for side-by-side comparison |

Profile/delta paper tables and duplicate stratified sections are omitted from HTML (copy buttons for those tables are not shown). Use `--format latex-only` to export all table IDs including `by_profile` and `variant_delta`.

## Generate report from smoke output

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v2.0-smoke \
  --manifest releases/paper-v2.0-smoke/manifest.yaml
```

## LaTeX-only copy pipeline

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v2.0-lock \
  --format latex-only \
  --table headline > /tmp/headline.tex
```

## Useful options

| Option | Purpose |
|--------|---------|
| `--table headline --table variant_delta` | Restrict LaTeX-only output scope |
| `--manifest releases/paper-v2.0/manifest.yaml` | Enrich drill-down with question + expected answer from bundle |
| `--delta-threshold 0.10` | Flag items with large metric gaps vs `graph-full` |
| `--max-item-rows 0` | Show all items in drill-down (default) |
| `--max-item-rows 500` | Truncate drill-down for very large runs |

## Item drill-down detail

Expand **Evaluation detail** on any row to see:

- Full question and expected answer (from custom-judge bundle when `--manifest` is set)
- Per-variant panels: full agent answer, judge scores, rationale, MRR/MAP/nDCG, citations, trajectory ref

Filters: profile, judge status, and highlight variant column.

## CI smoke expectation

Report generation must succeed offline on fixture or `paper-smoke` outputs:

```bash
uv run pytest tests/integration/test_repro_report_smoke.py -q
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| Missing `repro_run.json` | Verify `--input` points to repro root, not `tables/` |
| Missing `tables/*.csv` | Run `repro export-tables` or complete `repro run-all` |
| Empty drill-down section | Confirm `{variant}/results.json` exists and is valid JSON |
| Missing question/expected answer | Pass `--manifest releases/paper-v2.0/manifest.yaml` |
| Browser appears blank offline | Ensure output is self-contained HTML (no external assets) |
