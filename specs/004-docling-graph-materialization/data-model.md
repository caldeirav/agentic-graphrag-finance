# Data Model: Docling-Graph Knowledge Materialization

**Feature**: 004 | **Date**: 2026-05-21

## Graph node types (catalog)

| Type | Enum | Parent (CONTAIN) | Payload |
|------|------|------------------|---------|
| Document | `DOCUMENT` | — | `form_type`, `period_end`, `accession` |
| Section | `SECTION` | Document | `level`, `title` |
| Table | `CHUNK_TABLE` | Section or Document | `table_id`, `row_count` |
| Row | `CHUNK_ROW` | Table | row text / numeric cells |
| Paragraph | `CHUNK_PARAGRAPH` | Section | body text |
| XBRL fact | `CHUNK_XBRL_FACT` | Section (`{doc}-xbrl-facts`) | concept, value, period, currency, decimals |

**Migration note**: Today `GraphNodeType` lacks `CHUNK_XBRL_FACT`; facts use `CHUNK_PARAGRAPH`. Plan adds explicit type for audit clarity (FR-002).

## Graph edge types (catalog)

| Catalog name | Enum | Traversal role | Audit path |
|--------------|------|----------------|------------|
| Containment | `CONTAINS` | Parent → child hierarchy | **Yes** |
| Reading order | `NEXT` | Sequential sections/chunks | **Yes** |
| Footnote attachment | `FOOTNOTE_OF` | Chunk → footnote body | **Yes** |
| Cross-reference | `REFERENCES` | Chunk ↔ chunk in-filing | **Yes** |
| Temporal transition | `TEMPORAL_TRANSITION` | Document → document (issuer timeline) | No |
| Semantic similarity | `SEMANTIC_SIMILARITY` | Chunk ↔ chunk (cross-period/theme) | No |

### SEMANTIC_SIMILARITY metadata

```json
{
  "link_method": "deterministic | thematic",
  "concept_qname": "optional",
  "period_from": "optional ISO date",
  "period_to": "optional ISO date",
  "similarity_score": "0.0-1.0, thematic only",
  "confidence": "optional"
}
```

## ReachabilityAuditReport

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | str | Target snapshot |
| `issuer_id` | str | Issuer key |
| `hop_budget` | int | Default 6 |
| `sample_size` | int | ≥100 |
| `pass_rate` | float | 0.0–1.0 |
| `pass_threshold` | float | 0.95 |
| `audit_ready` | bool | `pass_rate >= pass_threshold` |
| `structural_edge_types` | list[str] | Allowed in path |
| `entries` | list[AuditEntry] | Per-fact results |
| `created_at` | datetime | UTC |
| `builder_version` | str | docling-graph mapper version |

### AuditEntry

| Field | Type |
|-------|------|
| `node_id` | str |
| `accession` | str |
| `node_kind` | `xbrl_fact \| table_row` |
| `reachable` | bool |
| `hop_count` | int \| null |
| `path_edge_types` | list[str] |
| `path_node_ids` | list[str] |

## FilingMaterializationResult

| Field | Type |
|-------|------|
| `accession` | str |
| `status` | `included \| failed` |
| `failure_reason` | str \| null |
| `node_count` | int |
| `edge_count` | int |
| `unresolved_footnotes` | int |
| `unresolved_cross_refs` | int |

## GraphManifest extensions (003 manifest)

Add optional fields to sidecar / index entry:

| Field | Type |
|-------|------|
| `graph_builder_version` | str | e.g. `docling-graph-mapper-1.0.0` |
| `audit_pass_rate` | float \| null |
| `audit_ready` | bool |
| `reachability_artifact` | str | path to `.reachability.json` |

## Validation rules

1. Published snapshot: every non-document node has exactly one CONTAIN chain to its `doc-{accession}` root.
2. `FOOTNOTE_OF` edges only when target footnote node exists.
3. `REFERENCES` edges only when both endpoints in same accession.
4. `SEMANTIC_SIMILARITY` with `link_method=deterministic` only between nodes with same `concept_qname` and different `period_end` on different documents.
5. Reachability audit MUST NOT use `TEMPORAL_TRANSITION` or `SEMANTIC_SIMILARITY` in path BFS.

## State transitions

```text
ParsedDocument[] → per-filing map → validate → include | fail
                → merge snapshot → similarity pass → temporal edges
                → save GraphML → reachability audit → audit_ready flag
```
