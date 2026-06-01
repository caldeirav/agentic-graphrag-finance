# Relevance Materialization Contract (012)

**Command**: `uv run agent-query repro materialize-relevance --manifest releases/{tag}/manifest.yaml`

## Inputs

- Published custom-judge bundle (`custom_judge_bundle_path`)
- `items/{eval_split}.jsonl`
- `corpus/graph_node_index.json` + graph snapshots referenced by bundle manifest

## Algorithm

For each accepted item in JSONL:

1. Resolve each `expected_section_path` to a section `node_id` via `graph_node_index`.
2. From each section node, traverse outgoing **`CONTAINS`** edges (and section→section hierarchy if indexed).
3. Collect nodes where `node_type` ∈ `{CHUNK_PARAGRAPH, CHUNK_XBRL_FACT, CHUNK_TABLE, CHUNK_ROW}`.
4. Deduplicate; sort by `node_id` ascending.
5. Write to item row `relevant_chunk_ids` and sidecar `relevance_labels.json`.

## Outputs

| Artifact | Description |
|----------|-------------|
| `items/dev.jsonl` | Updated rows (or copy to `items/dev.labeled.jsonl` if immutable publish policy) |
| `relevance_labels.json` | `{ labels_hash, coverage_rate, labels_by_item_id, failures[] }` |
| `relevance_report.json` | Human-readable failure listing |
| Updated 011 `manifest.json` fields | `relevance_labels_hash`, `relevance_coverage_rate`, `relevance_snapshot_id` |

## Hash (`labels_hash`)

SHA-256 of canonical JSON:

```json
{"labels_by_item_id": {"item-id": ["chunk-a", "chunk-b"], ...}}
```

Keys sorted by `item_id`; chunk ids sorted per item; UTF-8, LF.

## Gate (FR-008)

- `coverage_rate = (# items with len(relevant_chunk_ids) > 0) / (# accepted items)`
- MUST be ≥ 0.90 for `paper-v1.0` repro
- Exit code 1 with `relevance_report.json` on failure

## Idempotence

Re-running on unchanged corpus + paths MUST yield identical `labels_hash`.

## Layer boundary

- Module: `src/evaluation/reproduction/relevance.py`
- MAY import: `graph.store`, `models.enums.GraphNodeType`, bundle manifest readers
- MUST NOT import: `retrieval.orchestration`, `retrieval.service`
