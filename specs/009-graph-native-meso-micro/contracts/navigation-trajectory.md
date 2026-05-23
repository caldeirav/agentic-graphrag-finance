# Contract: Navigation Trajectory (009)

**Feature**: 009-graph-native-meso-micro | **Artifacts**: MLflow + console trace (007)

## MLflow artifact: `navigation_trace.json`

Required on every ask run where meso executes (including insufficient-evidence outcomes).

```json
{
  "meso_ranks": [
    {
      "section_node_id": "sec-...",
      "accession": "0000320193-26-000006",
      "rank": 1,
      "score": 0.88,
      "micro_eligible": true,
      "path": {
        "root_node_id": "doc-...",
        "terminal_node_id": "sec-...",
        "edge_type_sequence": ["CONTAINS", "CONTAINS"],
        "visits": []
      }
    }
  ],
  "micro_paths": [],
  "rejected_proposals": [],
  "visit_counts": { "meso": 12, "micro": 34, "total": 46 },
  "scan_ratio": 0.18,
  "budget_exhausted": false,
  "structural_edge_types_used": ["CONTAINS", "FOOTNOTE_OF"]
}
```

Each `visits[]` entry:

```json
{
  "stage": "micro",
  "source_node_id": "...",
  "edge_type": "FOOTNOTE_OF",
  "target_node_id": "...",
  "accession": "...",
  "hop_index": 2
}
```

## TrajectoryRecord extension

Add optional `navigation_trace: NavigationTraceRecord` alongside existing `macro_binding`, `graph_traversal` (legacy flat visits deprecated but may mirror for one release).

## Console trace (007)

Extend `build_meso_router_trace_payload` / `build_micro_extractor_trace_payload`:

| Field | Description |
|-------|-------------|
| `navigation_mode` | `graph_native` |
| `top_sections` | Up to 3 per filing with ranks |
| `edge_types_used` | Unique structural types |
| `visit_count` | Stage totals |
| `sample_path` | One human-readable hop chain |
| `rejected_count` | Validator rejections |
| `budget_exhausted` | bool |

Verbose depth: full `edge_type_sequence` per micro chunk used in synthesis.

## SC-001 / SC-002 compliance

- 100% traced runs include `edge_type` on every visit
- Console normal depth MUST show enough to open section/chunk (`node_id`, `accession`, first hop)

## Contract tests

- `tests/contract/test_navigation_trajectory_schema.py`
- `tests/integration/test_ask_navigation_trajectory.py` — MLflow artifact smoke
- `tests/integration/test_navigation_trace_usability.py` — five-query checklist (SC-002, manual sign-off doc)
