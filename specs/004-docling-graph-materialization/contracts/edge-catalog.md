# Contract: Graph Edge Type Catalog

**Feature**: 004-docling-graph-materialization | **Version**: 1.0.0

## Purpose

Single authoritative list of node and edge types for graph materialization, agent traversal, and reachability audit.

## Node types

| ID | Description |
|----|-------------|
| `DOCUMENT` | One per filing accession |
| `SECTION` | Docling section / MD&A block |
| `CHUNK_TABLE` | Parsed table |
| `CHUNK_ROW` | Table row |
| `CHUNK_PARAGRAPH` | Narrative body or footnote text |
| `CHUNK_XBRL_FACT` | One XBRL numeric fact instance (concept + period context) |

## Edge types

| ID | Direction | Metadata | Structural audit |
|----|-----------|----------|------------------|
| `CONTAINS` | parent → child | — | Yes |
| `NEXT` | prev → next | `order_index` optional | Yes |
| `FOOTNOTE_OF` | referrer → footnote | `ref_id` | Yes |
| `REFERENCES` | source → target | `ref_type` optional | Yes |
| `TEMPORAL_TRANSITION` | earlier doc → later doc | `period_from`, `period_to` | No |
| `SEMANTIC_SIMILARITY` | chunk ↔ chunk | `link_method`, `concept_qname`, `similarity_score` | No |

## Traversal policy

### Agent retrieval (default)

- Primary evidence navigation: `CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`
- Cross-period navigation (optional): `TEMPORAL_TRANSITION`, `SEMANTIC_SIMILARITY` (deterministic preferred over thematic)
- MUST NOT traverse off-catalog edges

### Reachability audit (SC-001)

- Allowed: `CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`
- Disallowed: `TEMPORAL_TRANSITION`, `SEMANTIC_SIMILARITY`
- Hop budget: **6** (configurable via `configs/graph_audit.yaml`)

## Layer boundary

- Published from `src/graph/edge_catalog.py`
- Imported by `graph/reachability.py`, `retrieval/orchestration` (read-only), tests
- MUST NOT be defined in `ingestion/` or `parsing/`
