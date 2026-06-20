# Contract: Dataset Review CLI (018)

**Feature**: 018-eval-dataset-quality | **Extends**: `benchmark-dataset` command group (011, 017)

## New subcommands

| Command | Purpose |
|---------|---------|
| `review export-queue` | Build prioritized review queue from repro + bundle |
| `review export-pack` | Export HTML + CSV review pack for item subset |
| `review annotate` | Append annotation to `annotations.jsonl` |
| `review apply-overrides` | Merge approved annotations into `items/dev.jsonl` |
| `review summary` | Emit `quality_pass_summary.json` from annotations + optional re-judge stats |
| `regenerate-item` | Per-slot Gemini regen with feedback constraints |
| `extend-quality` | Convenience wrapper: extend v2.0.0 → quality draft with sidecar files initialized |

## `review export-queue`

```bash
uv run agent-query benchmark-dataset review export-queue \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0 \
  --variant graph-full \
  --output review_queue
```

| Flag | Required | Description |
|------|----------|-------------|
| `--draft` | yes | Draft or published bundle root |
| `--repro-input` | no | Repro output dir; omit for structural-only queue |
| `--variant` | no | Default `graph-full` |
| `--output` | no | Basename; writes `{output}.json` and `{output}.csv` |

**Outputs**: `review_queue.json`, `review_queue.csv` per [review-queue-export.md](./review-queue-export.md).

## `review export-pack`

```bash
uv run agent-query benchmark-dataset review export-pack \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file review_queue_tier1.json \
  --repro-input reports/repro-paper-v1.0 \
  --output-dir data/benchmarks/custom-judge/drafts/quality-v2.0.1/review
```

| Flag | Required | Description |
|------|----------|-------------|
| `--draft` | yes | Bundle root |
| `--item-ids` | one of | Comma-separated ids |
| `--item-ids-file` | one of | JSON `item_ids[]` or stratified sample from `publish_audit.sample.json` |
| `--repro-input` | no | Include outcome/ranking columns |
| `--output-dir` | no | Default: draft root |

**Outputs**: `review_pack.html`, `review_pack.csv`.

## `review annotate`

```bash
uv run agent-query benchmark-dataset review annotate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finagentbench-0022 \
  --failure-class gt_boilerplate \
  --corpus-spot-check passed \
  --reviewer-id "${USER}" \
  --notes "Canonical answer is section co-occurrence only" \
  --proposed-overrides-file overrides/v2-finagentbench-0022.json
```

Appends one line to `annotations.jsonl`; never mutates `items/dev.jsonl`.

## `review apply-overrides`

```bash
uv run agent-query benchmark-dataset review apply-overrides \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --annotation-ids ann-001,ann-002 \
  --dry-run
```

1. Load annotations with `proposed_overrides` and `corpus_spot_check=passed`
2. Patch matching dev rows
3. Re-run v2 `validate_item` + feasibility/scorability gates
4. Append `override_changelog.jsonl` per item
5. Abort if any validation fails (no partial apply unless `--skip-failed`)

## `regenerate-item`

```bash
uv run agent-query benchmark-dataset regenerate-item \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finagentbench-0022 \
  --feedback-file feedback.txt \
  --dry-run
```

Replaces single dev row content via Gemini; preserves `item_id`; records changelog entry.

## Errors

| Condition | Exit |
|-----------|------|
| Missing `annotations.jsonl` parent draft | Create empty on first annotate |
| Apply without corpus spot-check passed | BadParameter |
| Override breaks v2 gate | Non-zero; changelog records `rejected` |
| Repro input missing for queue | Warning; tier-3 neutral priority only |

## Layer boundary

All commands live under `src/cli/commands/benchmark_dataset.py` facade; logic in `src/evaluation/generation/review/` (new package). MUST NOT import retrieval or ingestion fetch paths (011 boundary).
