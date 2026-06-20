# Quickstart: Evaluation Dataset Quality Pass (018)

**Feature**: 018-eval-dataset-quality | **Date**: 2026-06-20

## Prerequisites

- `uv sync --locked`
- Published `data/benchmarks/custom-judge/v2.0.0/` and completed `reports/repro-paper-v1.0/` (graph-full baseline)
- `.env` with `GOOGLE_API_KEY` for regenerate-item and re-judge
- Branch `018-eval-dataset-quality`

## Phase 1 — Extend quality draft from v2.0.0

```bash
uv run agent-query benchmark-dataset extend \
  --parent-version 2.0.0 \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id quality-v2.0.1
```

Verify draft contains empty sidecars (created on first use):
- `annotations.jsonl`
- `override_changelog.jsonl`

## Phase 2 — Export review queue (repro-driven)

```bash
uv run agent-query benchmark-dataset review export-queue \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0 \
  --variant graph-full \
  --tier 1 \
  --output review_queue_tier1
```

Inspect `review_queue_tier1.json` — expect tier-1 items (MRR ≥ 0.5 or nDCG@10 ≥ 0.3, outcome = 0) ranked first.

## Phase 3 — Export review pack (20-item audit)

```bash
uv run agent-query benchmark-dataset review export-pack \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file review_queue_tier1.json \
  --max-items 20 \
  --repro-input reports/repro-paper-v1.0 \
  --output-dir data/benchmarks/custom-judge/drafts/quality-v2.0.1
```

Open `review_pack.html` in browser; use `review_pack.csv` for annotation workflow.

## Phase 4 — Annotate and apply overrides

```bash
# Example annotation
uv run agent-query benchmark-dataset review annotate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finagentbench-0022 \
  --failure-class gt_boilerplate \
  --corpus-spot-check passed \
  --reviewer-id "${USER}" \
  --proposed-overrides-file path/to/override.json

# Apply all eligible annotations
uv run agent-query benchmark-dataset review apply-overrides \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1
```

For stubborn items, regenerate in place:

```bash
uv run agent-query benchmark-dataset regenerate-item \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finagentbench-0022 \
  --feedback-file feedback.txt
```

Re-run feasibility/scorability:

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --version 2.0.1 \
  --dry-run
```

## Phase 5 — Selective re-judge (validate fixes)

```bash
# fixed_items.json: {"item_ids": ["v2-finagentbench-0022", ...]}
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variant graph-full \
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file fixed_items.json \
  --force-rescore
```

```bash
uv run agent-query benchmark-dataset review summary \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0
```

**Targets**: dataset-caused zero-score rate < 15%; majority of fixed items show improved outcome scores.

## Phase 6 — Publish v2.0.1

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --version 2.0.1 \
  --publish-signoff \
  --operator-id "${USER}"
```

Gates include: `boilerplate_comparison_count: 0`, existing v2 gates, 20-item audit.

## Phase 7 — paper-v1.1 release lock

```bash
# Create releases/paper-v1.1/manifest.yaml (parent: paper-v1.0, bundle: v2.0.1)
uv run agent-query repro run-all \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-paper-v1.1

uv run agent-query repro verify-tables \
  --manifest releases/paper-v1.1/manifest.yaml \
  --input reports/repro-paper-v1.1
```

Record `releases/paper-v1.1/expected_checksums.json`. paper-v1.0 remains unchanged.

## Phase 8 — Diversity governance (optional regen)

For net-new generation with improved diversity (SC-004):

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2_quality.yaml \
  --run-id diversity-pilot \
  --phase judge \
  --target-items 20
```

Compare `diversity_report.json` duplicate rate vs v2.0.0 baseline (~40%).

## Troubleshooting

| Issue | Action |
|-------|--------|
| Tier-1 queue empty | Verify repro completed; check `graph-full/results.json` has ranking_metrics |
| Apply-overrides blocked | Check `corpus_spot_check=passed`; run item_validator errors |
| Boilerplate gate fails | Rewrite canonical answer with cross-verb conclusion; see comparison-boilerplate-gate contract |
| Re-judge unchanged scores | Confirm `--bundle-override` points at draft with updated GT |
