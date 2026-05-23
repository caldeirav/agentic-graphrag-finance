# Contract: Graph Navigation Policy (009)

**Feature**: 009-graph-native-meso-micro | **Version**: 1.0.0

## Purpose

Authoritative rules for meso/micro graph traversal: allowed edges, scope, budgets, and meso→micro handoff.

## Allowed edge types (agent)

From `graph.edge_catalog.STRUCTURAL_EDGE_TYPES` only:

| Edge | Use |
|------|-----|
| `CONTAINS` | Document→section, section→table/paragraph, table→row |
| `NEXT` | Sibling order within parent |
| `FOOTNOTE_OF` | Table/paragraph → footnote |
| `REFERENCES` | Cross-reference between narrative nodes |

**Forbidden for agent hops**: `TEMPORAL_TRANSITION`, `SEMANTIC_SIMILARITY`.

## Scope

- Meso starts at each `DOCUMENT` node whose accession ∈ `filing_set`.
- Micro starts at each `SECTION` in top-3 meso ranks per filing.
- Validator MUST reject hops where target’s document root accession ∉ `filing_set`.

## Meso → micro handoff

- Rank all sections reached or explicitly scored during meso walk.
- Pass **top 3 sections per filing** to micro (`micro_eligible=true` on `MesoRankRecord`).
- Lower ranks: present in `meso_ranks` and trace only.

## Budgets

Loaded from `configs/graph_navigation.yaml` (see [research.md](../research.md) R6). Walker MUST stop and set `stop_reason=budget` when any cap exceeded.

## Production paths

| Path | Allowed |
|------|---------|
| Graph-native meso + micro (default) | Yes |
| Heuristic flat section list / global chunk scan | **No** (FR-013) |
| Full-graph enumeration | Diagnostic/CI flag only; invalidates SC-003 |

## Layer boundary

- Policy constants: `graph/edge_catalog.py`
- Enforcement: `retrieval/navigation/validator.py`
- Orchestration: `retrieval/orchestration/nodes/meso_router.py`, `micro_extractor.py`
