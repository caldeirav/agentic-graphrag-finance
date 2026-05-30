# Dataset Bundle Manifest Contract (011)

**Artifact**: `data/benchmarks/custom-judge/v{version}/manifest.json`

## Schema (`schema_version: 1.0.0`)

```json
{
  "schema_version": "1.0.0",
  "dataset_name": "custom-judge",
  "version": "1.0.0",
  "status": "published",
  "parent_version": null,
  "item_count": 210,
  "items_hash": "sha256:…",
  "sampling_manifest_path": "sampling_manifest.json",
  "generation_config_path": "generation_config.yaml",
  "generation_report_path": "generation_report.json",
  "generation_judge_version": "gemini-2.5-pro",
  "evaluation_judge_version": "gemini-2.5-pro",
  "profile_counts": {
    "financebench": 71,
    "finder": 70,
    "finagentbench": 69
  },
  "corpus_bundle": {
    "snapshot_id": "composite-a1b2c3…",
    "corpus_root": "corpus",
    "graph_node_index_path": "corpus/graph_node_index.json",
    "total_bytes": 2147483648,
    "artifact_hashes": {
      "corpus/graphs/AAPL/{snapshot_id}/snapshot.json": "sha256:…"
    },
    "issuer_snapshots": [
      {
        "ticker": "AAPL",
        "snapshot_id": "d7600d84-…",
        "relative_path": "corpus/graphs/AAPL/d7600d84-…"
      }
    ]
  },
  "published_at": "2026-05-20T18:00:00Z",
  "published_by": "operator"
}
```

## Draft manifest differences

- `status`: `"draft"`
- `published_at` / `published_by`: omitted
- Lives under `drafts/{run_id}/` until publish copies to versioned path

## Integrity

- `items_hash`: SHA-256 of normalized JSONL (sorted by `item_id`, UTF-8, LF)
- `reproduce` recomputes and compares
- LFS files verified via `artifact_hashes` after `git lfs pull`

## MLflow (evaluation runs)

Log params on benchmark parent run:
- `custom_judge_version`
- `custom_judge_items_hash`
- `generation_judge_version`
- `evaluation_judge_version`
- `generation_seed`

Log artifact: copy of `manifest.json` as `custom_judge_manifest.json`
