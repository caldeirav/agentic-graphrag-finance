# Release Manifest Contract (012)

**Artifact**: `releases/{tag}/manifest.yaml` (e.g. `releases/paper-v1.0/manifest.yaml`)

## Schema (`schema_version: 1.0.0`)

```yaml
schema_version: "1.0.0"
release_tag: paper-v1.0
git_sha: "abc123…"
custom_judge_version: "1.0.0"
custom_judge_bundle_path: data/benchmarks/custom-judge/v1.0.0
eval_split: dev
reproduction_mode: live_reexecution

corpus_hashes:
  corpus/graph_node_index.json: "sha256:…"
  # subset of 011 artifact_hashes required for verify-corpus

relevance_labels_hash: "sha256:…"  # gate: must match after materialize
relevance_coverage_rate: 0.94

variant_ids:
  - graph-full
  - flat-chunk
  - ablation-no-macro
  - ablation-no-walker
  - ablation-xbrl-only

model_pins:
  llm_config_path: configs/llm/lm_studio_qwen.yaml
  llm_config_hash: "sha256:…"
  judge_config_path: configs/judges/gemini_2_5_pro.yaml
  judge_config_hash: "sha256:…"
  embedding_model_id: sentence-transformers/all-MiniLM-L6-v2
  embedding_config_path: configs/reproduction/embeddings/all_minilm_l6_v2.yaml

tolerance_bands:
  mean_outcome_accuracy: 0.02
  mean_rubric_alignment: 0.02
  mean_trajectory_fidelity: 0.02
  ranking_metrics_exact: true
  structural_metrics_exact: true

expected_checksums_path: expected_checksums.json
```

## Companion: `expected_checksums.json`

```json
{
  "headline": {
    "graph-full.mean_ndcg_at_10": 0.4123456789,
    "flat-chunk.mean_ndcg_at_10": 0.3012345678
  },
  "by_profile": {},
  "structural_exact": true
}
```

## Validation gates

1. `git rev-parse HEAD` MUST match `git_sha` when `--strict-git` (default for paper-v1.0).
2. All `corpus_hashes` MUST match bundled files after `git lfs pull`.
3. `relevance_coverage_rate` ≥ 0.90 or repro aborts before variant runs.
4. `variant_ids` length MUST be 5 for `paper-v1.0`.

## MLflow params (parent repro run)

Log on `repro run-all` parent:
- `release_tag`, `git_sha`, `custom_judge_version`, `relevance_labels_hash`
- Per-variant child runs: `variant_id`, `embedding_model_id`, judge/LLM config hashes
