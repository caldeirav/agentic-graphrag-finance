# Quickstart: Research Reproduction Results Viewer (014)

**Feature**: 014-repro-results-viewer

## Generate the HTML report

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0/report.html
```

## LaTeX copy

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --format latex-only --table headline
```

## Options

| Option | Purpose |
|--------|---------|
| `--manifest releases/paper-v1.0/manifest.yaml` | Question + expected answer enrichment |
| `--max-item-rows 0` | All items in drill-down (default) |
| `--delta-threshold 0.10` | Flag large gaps vs `graph-full` |

See [research-reproduction.md](../../docs/research-reproduction.md) for the full **paper-v1.0** workflow.
