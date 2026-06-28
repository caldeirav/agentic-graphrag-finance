# Contract: Failure Investigation Pack Export

**Feature**: 019 | **Layer**: evaluation/reproduction/investigation

## CLI

```bash
uv run agent-query benchmark-dataset review export-investigation \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --repro-input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/investigation \
  [--variant graph-full]
```

Also invoked as part of:

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --manifest releases/paper-v1.0/manifest.yaml \
  [--with-investigation]
```

## Outputs

| File | Description |
|------|-------------|
| `failure_investigation.html` | Static offline pack for all queue items |
| `failure_investigation.csv` | Same rows as HTML |
| `graph_context/{item_id}.html` | Optional per-item subgraph panel (link target) |

## Row schema

See `data-model.md` → `FailureInvestigationRow`. CSV columns MUST match HTML table fields.

## Behavior

- Missing repro result for queue item: row rendered with `repro_missing: true`; taxonomy uses partial signals
- Missing corpus section text: `corpus_excerpts[].source = pointer`
- EDGAR links per `edgar-filing-links.md`
- `suggested_failure_class` populated by `taxonomy-suggestion.md` rules
- Drill-down in repro report MUST call same row builder (no field drift)

## Non-goals

- Does not mutate bundle or repro results
- Does not re-run agent or judge
