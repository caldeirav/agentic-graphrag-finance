# Contract: paper-v1.1 Release (018)

**Feature**: 018-eval-dataset-quality | **Parent**: [paper-v1.0](../../012-research-repro-kit/contracts/release-manifest.md)

## Release layout

```text
releases/paper-v1.1/
├── manifest.yaml
├── expected_checksums.json
└── smoke_dev_item_ids.json          # copy or regenerate from v2.0.1
```

## manifest.yaml deltas from paper-v1.0

| Field | paper-v1.0 | paper-v1.1 |
|-------|------------|------------|
| `release_tag` | paper-v1.0 | paper-v1.1 |
| `custom_judge_version` | 2.0.0 | 2.0.1 |
| `custom_judge_bundle_path` | .../v2.0.0 | .../v2.0.1 |
| `items_hash` | sha256:f326... | NEW (distinct) |
| `corpus_hashes` | unchanged | **SAME** (in-place patch, no corpus regen) |
| `relevance_labels_hash` | unchanged | MAY refresh if chunk labels change |
| `parent_release` | — | paper-v1.0 |

## Adoption workflow

1. Publish `data/benchmarks/custom-judge/v2.0.1/` from quality draft
2. `repro materialize-relevance --manifest releases/paper-v1.1/manifest.yaml` (if labels refresh)
3. Full `repro run-all --manifest releases/paper-v1.1/manifest.yaml`
4. Record `expected_checksums.json` from baseline repro
5. Document delta vs paper-v1.0 in release notes (dataset-caused zero-score rate, task_success)

## Immutability

- `releases/paper-v1.0/` MUST NOT be modified
- `data/benchmarks/custom-judge/v2.0.0/` MUST NOT be modified

## Selective re-judge (pre-full-repro)

For quality validation during draft iteration:

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variant graph-full \
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file fixed_items.json \
  --force-rescore
```

Uses updated GT from override bundle; same agent answers from checkpoints.
