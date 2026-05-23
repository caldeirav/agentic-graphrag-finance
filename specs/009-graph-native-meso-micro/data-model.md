# Data Model: Graph-Native Meso and Micro Navigation (009)

**Branch**: `009-graph-native-meso-micro` | **Date**: 2026-05-23

## Overview

Meso and micro stages produce **validated navigation traces** and **evidence chunks** after macro binding. Flow: `filing_set` → per-filing meso walk from `DOCUMENT` roots → ranked sections → top 3 per filing → per-section micro walk → `evidence_chunks` + `NavigationTraceRecord` in `AgentState` → MLflow `navigation_trace.json` + console trace (007).

## Entities

### HopProposal (new)

LLM output for one navigation step; not trusted until validated.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `stage` | enum | yes | `meso` \| `micro` |
| `source_node_id` | string | yes | Current position |
| `candidates` | list[HopCandidate] | yes | 1–3 items |
| `intent_note` | string | no | Short rationale for trace |
| `proposal_source` | enum | yes | `llm` \| `mock` |

### HopCandidate (new)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `target_node_id` | string | yes | Proposed next node |
| `edge_type` | GraphEdgeType | yes | Must be structural |
| `direction` | enum | yes | `outgoing` \| `incoming` (for undirected traversal) |
| `score` | float | no | LLM self-rank |

### HopValidationResult (new)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | enum | yes | `approved` \| `rejected` |
| `approved_hop` | NavigationVisit | no | Set when approved |
| `rejection_code` | string | no | e.g. `disallowed_edge`, `out_of_scope`, `budget_exceeded` |
| `rationale` | string | yes | |

### NavigationVisit (new)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `stage` | enum | yes | `meso` \| `micro` |
| `source_node_id` | string | yes | |
| `edge_type` | GraphEdgeType | yes | |
| `target_node_id` | string | yes | |
| `accession` | string | yes | Derived from document root |
| `hop_index` | int | yes | 0-based within stage scope |
| `stop_reason` | string | no | `budget`, `dead_end`, `target_reached` |

### NavigationPath (new)

Ordered visits from a root (document or section) to a terminal node (section for meso, chunk for micro).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `root_node_id` | string | yes | |
| `terminal_node_id` | string | yes | |
| `visits` | list[NavigationVisit] | yes | |
| `edge_type_sequence` | list[string] | yes | Denormalized for SC-004 |
| `chunk_node_ids` | list[string] | no | Micro paths ending at evidence |

### MesoRankRecord (new)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `section_node_id` | string | yes | |
| `accession` | string | yes | |
| `rank` | int | yes | 1-based |
| `score` | float | yes | From walk termination or LLM rank |
| `path` | NavigationPath | yes | Full meso path to section |
| `micro_eligible` | bool | yes | `rank <= 3` |

### NavigationTraceRecord (new, trajectory)

Persisted to MLflow and embedded in `TrajectoryRecord`.

| Field | Type | Notes |
|-------|------|-------|
| `meso_paths` | list[NavigationPath] | All meso walks attempted |
| `meso_ranks` | list[MesoRankRecord] | Sorted |
| `micro_paths` | list[NavigationPath] | Per eligible section |
| `rejected_proposals` | list[dict] | Proposal + `HopValidationResult` |
| `visit_counts` | dict | `meso`, `micro`, `total` |
| `scan_ratio` | float | For eval harness |
| `budget_exhausted` | bool | |
| `structural_edge_types_used` | list[string] | Unique edge types |

### SectionCandidate (extended)

Existing `models/query.py` fields; extend:

| Field | Type | Notes |
|-------|------|-------|
| `path` | list[string] | **Replace** bare node id list with visit-derived ids |
| `edge_types` | list[string] | Parallel to path hops |
| `accession` | string | Filing membership |

### EvidenceChunk (extended)

| Field | Type | Notes |
|-------|------|-------|
| `navigation_path_id` | string | Links to `NavigationPath` in trace |
| `edge_types` | list[string] | Hops used to reach chunk |

## State transitions (`AgentState`)

```text
[macro_router approved]
  → meso_router
       FOR each filing in filing_set:
         start at DOCUMENT root
         LOOP: LLM HopProposal → validate → NavigationVisit until budget or section targets ranked
       rank sections → meso_ranks (top N)
       select top 3 per filing → micro_eligible_section_ids
  → micro_extractor
       FOR each eligible section:
         LOOP: LLM HopProposal → validate → visit until chunk nodes collected or budget
       merge chunks (dedupe by node_id, retain paths)
  → synthesize (unchanged grounding rule)
```

### Failure / insufficient evidence

- No micro chunks after walks → `status=INSUFFICIENT_EVIDENCE`, `navigation_trace` still populated
- No heuristic fallback fields written

## Validation rules (validator)

1. `edge_type ∈ STRUCTURAL_EDGE_TYPES`
2. `target_node_id` must be neighbor of `source_node_id` via declared edge in snapshot
3. Both nodes resolve to document root accession ∈ `filing_set` accessions
4. Cumulative visits ≤ `query.max_total_visits`
5. Stage-specific hop/visit caps from `graph_navigation.yaml`
6. Reject `TEMPORAL_TRANSITION`, `SEMANTIC_SIMILARITY` with `rejection_code=disallowed_edge`

## Layer boundaries

| Layer | Owns |
|-------|------|
| `graph/edge_catalog.py` | Structural vs cross-filing edge sets |
| `graph/query_api.py` | Neighbor enumeration, navigable counts |
| `retrieval/navigation/` | Planner, validator, walker loops |
| `retrieval/orchestration/nodes/` | Wire meso_router / micro_extractor |
| `tracing/` | `navigation_trace.json`, console payloads |
| `evaluation/metrics/gold_path.py` | SC-003/SC-004 metrics only |

Evaluation MUST NOT import `retrieval.navigation.planner`.
