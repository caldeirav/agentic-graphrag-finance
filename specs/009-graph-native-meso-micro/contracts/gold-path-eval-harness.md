# Contract: Gold-Path Evaluation Harness (009)

**Feature**: 009-graph-native-meso-micro | **Version**: 1.0.0

## Dataset

**Path (CI)**: `tests/fixtures/gold_path/gold_path.jsonl`  
**Minimum items**: 40 (target 50 at task generation)  
**Corpus**: Fixed `aapl_macro_snapshot` (same family as 008 macro eval)

### Row schema

```json
{
  "id": "gp-001",
  "query": "What was revenue in the prior quarter?",
  "expected_accessions": ["0000320193-26-000057"],
  "required_chunk_node_ids": ["chunk-xbrl-us-gaap-Revenues-..."],
  "acceptable_edge_sequences": [
    ["CONTAINS", "CONTAINS"]
  ],
  "multi_filing_required": false,
  "notes": "optional rubric"
}
```

## Metrics

| Metric | Success criterion | Implementation |
|--------|-------------------|----------------|
| `chunk_reach_rate` | ≥ 75% items reach all `required_chunk_node_ids` | `evaluation/metrics/gold_path.py` |
| `path_match_rate` | ≥ 90% of reached items match `acceptable_edge_sequences` (or rubric equivalent) | prefix match on `edge_type_sequence` |
| `scan_ratio` | Per item; fail SC-003 if ≥ 0.90 before chunk reached | `navigable_node_count` from graph API |
| `grounding_rate` | 100% on subset with synthesis assertions | reuse grounding helper |

**Full-graph scan**: `scan_ratio >= 0.90` before required chunk retrieved (per spec SC-003).

## CLI

```bash
USE_MOCK_LLM=1 uv run agent-query test --gold-path --ticker AAPL
```

Registers benchmark slice `gold_path` in FinAgentBench loader (evaluation layer only).

## CI gate

- `tests/integration/test_gold_path_benchmark.py` — mock LLM, fixture snapshot, assert `chunk_reach_rate >= 0.75`
- Does not require `data/` tree

## Generator (optional tooling)

`src/cli/gold_path_labeler.py` — offline script to propose labels from mock navigation on snapshot; output to fixtures, not committed `data/`.

## Layer boundary

- Harness imports: `evaluation.*`, published trajectory JSON schema
- Harness MUST NOT import: `retrieval.navigation.planner`, `retrieval.orchestration.nodes`
