# Contract: paper-v2.0 Release Lock (017)

**Path**: `releases/paper-v2.0/manifest.yaml`

## Purpose

Distinct reproduction lock from paper-v1.0. Pins bundle v2.0.0, refreshed hashes, and **mandatory full agent re-run** on all five variants × 200 items.

## Required fields

```yaml
schema_version: "1.0.0"
release_tag: paper-v2.0
git_sha: <pinned at publish time>
custom_judge_version: "2.0.0"
custom_judge_bundle_path: data/benchmarks/custom-judge/v2.0.0
eval_split: dev
reproduction_mode: live_reexecution

corpus_hashes:
  corpus/graph_node_index.json: "sha256:..."

items_hash: "<from bundle manifest>"
relevance_labels_hash: "<regenerated>"
relevance_coverage_rate: 1.0

variant_ids:
  - graph-full
  - flat-chunk
  - ablation-no-macro
  - ablation-no-walker
  - ablation-xbrl-only

model_pins:
  llm_config_path: configs/llm/lm_studio_qwen.yaml
  judge_config_path: configs/judges/gemini_2_5_pro.yaml
  # ... hashes TBD at baseline repro

full_reproduction_policy:
  selective_agent_skip: false
  changelog_based_skip: false
  required_variants: 5
  required_items_per_variant: 200

tolerance_bands:
  mean_task_success: 0.02
  ranking_metrics_exact: true
  structural_metrics_exact: true
```

## Hash distinctness (acceptance)

All of the following MUST differ from `releases/paper-v1.0/manifest.yaml`:

- `corpus_hashes.*`
- `items_hash`
- `relevance_labels_hash`
- `custom_judge_version`

## Reproduction acceptance

A paper-v2.0 reproduction is **complete** when:

1. All five variants have agent results for all 200 dev items
2. Judge-batch completes with judge version ≥ v3.1 and VA present on ≥95% of items
3. Export produces task_success n=200 per `task-success-v2.md`
4. Report generated without rubric_alignment headline row

## Immutability

- `releases/paper-v1.0/` and `data/benchmarks/custom-judge/v1.2.0/` MUST NOT be modified when publishing paper-v2.0
- paper-v2.0 baseline checksums recorded in `releases/paper-v2.0/expected_checksums.json` after first full repro

## CLI

```bash
uv run agent-query repro run --release paper-v2.0 --tag paper-v2.0
uv run agent-query repro judge-batch --input reports/repro-paper-v2.0
uv run agent-query repro export-tables --input reports/repro-paper-v2.0
uv run agent-query repro report --input reports/repro-paper-v2.0
```
