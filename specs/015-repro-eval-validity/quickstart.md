# Quickstart: Reproduction Evaluation Validity & Stratified Ablations (015)

**Feature**: 015-repro-eval-validity | **Date**: 2026-06-06

## Prerequisites

- Existing reproduction output (`reports/repro-paper-v1.0/` or smoke)
- P0 scoring fixes on current branch (`main` or rebased feature branch)
- Judge API credentials for re-score
- Custom-judge bundle at path in release manifest

## Re-score paper-v1.0 (P1)

Re-run deferred judge on all variants without re-executing agents:

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0
```

Resume skips items already at judge v2 with hydrated trajectory evidence. Force full refresh:

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --force-rescore
```

Re-export tables and regenerate report:

```bash
uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

### Verify SC-001

Check `tables/headline.csv`:

- `graph-full` `outcome_accuracy` > `ablation-no-walker`
- `graph-full` `outcome_accuracy` > `ablation-xbrl-only`
- Ranking: `graph-full` MRR/nDCG still above `flat-chunk`

## Structural metrics smoke (P1)

After a binding-heavy smoke run:

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-live-smoke/manifest.yaml \
  --max-items 10
```

Inspect `reports/repro-paper-smoke/repro_run.json` → `variant_runs[].structural_metrics` for non-zero values.

## Investigation report (P2)

Open regenerated `report.html`:

- Investigation notes section should show ≤ 25 aggregated entries
- Expected ablation abstention appears once per pattern (not per item)
- Expand a note to see up to 5 example item ids

## Stratified tables (P3)

After export with P3 implemented:

```bash
ls reports/repro-paper-v1.0/tables/by_evidence_source.csv
ls reports/repro-paper-v1.0/tables/variant_delta_by_source.csv
```

Report includes stratified ablation section per evidence source.

Copy HTML-stratum delta for paper:

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --format latex-only \
  --table variant_delta_by_source
```

(Table id available after P3 `PaperTableId` extension.)

## Troubleshooting

| Symptom | Action |
|---------|--------|
| Outcome still inverted | Confirm P0 on branch; run `--force-rescore` |
| Rubric alignment all 0 | Check judge populates `claim_presence` / `value_alignment` |
| Structural metrics all 0 | Re-run variant or backfill from checkpoints after P1 wiring |
| 500+ investigation notes | Regenerate report after P2 aggregation |
| Missing stratum CSVs | Run `export-tables` after P3; old checkpoints lack files (warn only) |

## Related docs

- [re-judge-workflow.md](./contracts/re-judge-workflow.md)
- [stratum-export.md](./contracts/stratum-export.md)
- [014 quickstart](../014-repro-results-viewer/quickstart.md)
- [research-reproduction.md](../../docs/research-reproduction.md)
