# Data Model: Agentic SEC Disclosure Reasoning & Benchmarking

**Date**: 2026-05-18 | **Plan**: [plan.md](./plan.md)

All cross-layer payloads are **Pydantic v2** models in `src/models/` (re-exported by layer packages). IDs are stable strings (UUID or deterministic hash suffix).

---

## Parsing Layer

### `FilingRef`

| Field | Type | Description |
|-------|------|-------------|
| `cik` | str | SEC CIK (zero-padded) |
| `accession` | str | EDGAR accession number |
| `form_type` | Literal["10-K","10-Q",...] | Filing type |
| `filed_at` | date | Filing date |
| `period_end` | date | Reporting period end |
| `source_uri` | str | EDGAR URL or local path |

### `TableBlock`

| Field | Type | Description |
|-------|------|-------------|
| `table_id` | str | Stable id |
| `headers` | list[list[str]] | Header rows (supports multi-row) |
| `rows` | list[list[str]] | Body rows |
| `merged_cells` | list[CellSpan] | Optional merged regions |
| `footnote_ids` | list[str] | Linked footnotes |

### `ParsedDocument`

| Field | Type | Description |
|-------|------|-------------|
| `filing` | FilingRef | Source identity |
| `sections` | list[SectionBlock] | Hierarchical sections |
| `tables` | list[TableBlock] | Extracted tables |
| `footnotes` | list[FootnoteBlock] | Nested footnote bodies |
| `parse_confidence` | float | 0–1 aggregate QA score |
| `parser_version` | str | Docling + config hash |
| `content_hash` | str | SHA-256 of raw filing bytes |

**Validation**: `parse_confidence < threshold` → fail-closed; not eligible for graph build without override flag.

---

## Graph Layer

### Node types (`GraphNodeType` enum)

- `DOCUMENT`
- `SECTION`
- `CHUNK_TABLE` | `CHUNK_ROW` | `CHUNK_PARAGRAPH`

### `GraphNode`

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | str | Primary key |
| `node_type` | GraphNodeType | Discriminator |
| `label` | str | Human title (e.g., "Consolidated Balance Sheets") |
| `properties` | dict | Type-specific (period, units, cell coords) |
| `source_ref` | str | Pointer into ParsedDocument |

### Edge types (`GraphEdgeType` enum)

- `CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`, `TEMPORAL_TRANSITION`

### `GraphEdge`

| Field | Type | Description |
|-------|------|-------------|
| `edge_id` | str | Primary key |
| `source_id` | str | Tail node |
| `target_id` | str | Head node |
| `edge_type` | GraphEdgeType | Relationship kind |
| `properties` | dict | e.g., `period_from`, `period_to` |

### `GraphSnapshot`

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | str | Immutable corpus version |
| `issuer_id` | str | CIK or ticker canonical id |
| `nodes` | list[GraphNode] | Full node list |
| `edges` | list[GraphEdge] | Full edge list |
| `manifest` | GraphManifest | Metadata |

### `GraphManifest`

| Field | Type | Description |
|-------|------|-------------|
| `created_at` | datetime | Build timestamp |
| `filing_refs` | list[FilingRef] | Included filings |
| `parser_version` | str | From ParsedDocument |
| `graph_builder_version` | str | docling-graph + mapper version |
| `storage_path` | str | GraphML path |

---

## Retrieval Layer (LangGraph `AgentState`)

### `AgentState` (TypedDict or Pydantic)

| Field | Type | Set by |
|-------|------|--------|
| `query` | str | Input |
| `snapshot_id` | str | Input |
| `macro_plan` | MacroPlan | macro_router |
| `filing_set` | list[FilingRef] | macro_router |
| `section_candidates` | list[SectionCandidate] | meso_router |
| `evidence_chunks` | list[EvidenceChunk] | micro_extractor |
| `answer` | AnswerPackage \| None | synthesize |
| `status` | QueryStatus | synthesize |
| `mlflow_run_id` | str \| None | tracing wrapper |

### `MacroPlan`

| Field | Type | Description |
|-------|------|-------------|
| `intent_summary` | str | Parsed question intent |
| `temporal_scope` | TemporalScope | Periods to compare |
| `rationale` | str | Model reasoning (logged) |

### `TemporalScope`

| Field | Type | Description |
|-------|------|-------------|
| `anchor_periods` | list[date] | Target reporting periods |
| `comparison_mode` | enum | YoY, QoQ, sequential quarters |

### `SectionCandidate`

| Field | Type | Description |
|-------|------|-------------|
| `section_node_id` | str | Graph section node |
| `score` | float | Meso rank |
| `path` | list[str] | Node id path from document root |

### `EvidenceChunk`

| Field | Type | Description |
|-------|------|-------------|
| `chunk_node_id` | str | Graph chunk node |
| `excerpt` | str | Exact text or serialized cell value |
| `content_hash` | str | Hash of excerpt bytes |
| `citation_label` | str | Display citation |

### `AnswerPackage`

| Field | Type | Description |
|-------|------|-------------|
| `text` | str | Final narrative answer |
| `citations` | list[EvidenceChunk] | Supporting evidence |
| `sufficiency` | Literal["complete","partial","insufficient"] | |

### `QueryStatus`

`SUCCESS` | `INSUFFICIENT_EVIDENCE` | `ERROR`

---

## Tracing

### `TrajectoryRecord` (MLflow artifact)

| Field | Type | Constitution mapping |
|-------|------|----------------------|
| `plan` | MacroPlan + node rationales | Plan |
| `document_route` | list[FilingRef] + section paths | Document route |
| `graph_traversal` | list[GraphVisit] | Graph nodes/edges visited |
| `evidence` | list[EvidenceChunk] | Evidence chunks |

### `GraphVisit`

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | str | Visited node |
| `edge_id` | str \| None | Traversed edge |
| `stage` | Literal["macro","meso","micro"] | Routing stage |

---

## Evaluation Layer

### `BenchmarkItem`

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | str | Unique within dataset |
| `dataset` | str | finder \| finagentbench \| financebench |
| `question` | str | Benchmark query |
| `ground_truth` | GroundTruth \| None | Answer / rubric |
| `relevant_chunk_ids` | list[str] \| None | For MRR/MAP/nDCG |
| `operation_class` | OperationClass | Stratification tag |

### `OperationClass` enum

`QUALITATIVE` | `ADD` | `SUB` | `MUL` | `DIV` | `COMPOSITIONAL`

### `EvaluationRun`

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | str | UUID |
| `suite_name` | str | e.g., `pilot` |
| `snapshot_id` | str | Frozen graph corpus |
| `judge_config_id` | str | Pinned Gemini config |
| `items` | list[BenchmarkResult] | Per-item outcomes |

### `BenchmarkResult`

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | str | |
| `answer` | AnswerPackage | System output |
| `mlflow_run_id` | str | Retrieval trace link |
| `outcome_score` | float | Judge: correctness |
| `alignment_score` | float | Judge: factual alignment |
| `trajectory_fidelity` | float | Judge: process quality |
| `ranking_metrics` | RankingMetrics \| None | MRR, MAP, nDCG@k |

### `JudgeVerdict`

| Field | Type | Description |
|-------|------|-------------|
| `judge_model` | str | e.g., gemini-2.5-pro |
| `judge_version` | str | Config hash |
| `rationale` | str | Short explanation |
| `scores` | dict[str, float] | Dimension → score |

---

## State Transitions (Query Lifecycle)

```text
[Query submitted]
    → macro_router (select filings / temporal scope)
    → meso_router (rank sections)
    → micro_extractor (select chunks)
    → synthesize
        → SUCCESS (answer + citations)
        → INSUFFICIENT_EVIDENCE (no fabricated numbers)
        → ERROR (technical failure)
[MLflow run closed with TrajectoryRecord artifact]
```

```text
[Benchmark batch]
    → For each BenchmarkItem: QueryService.answer
    → Gemini judge: outcome + alignment + trajectory
    → Aggregate RankingMetrics + stratified report by OperationClass
```
