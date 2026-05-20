# Research: Docling-Graph Knowledge Materialization

**Feature**: 004-docling-graph-materialization | **Date**: 2026-05-21

## R1: docling-graph as sole mapper

**Decision**: Use `docling-graph` to produce hierarchical ER output from each `ParsedDocument`, then normalize into internal `GraphSnapshot` (`GraphNode`, `GraphEdge`, NetworkX/GraphML via existing store).

**Rationale**: Aligns with 001 R3; user clarification mandates **replace** custom builder, not dual-run. Dependency already in `pyproject.toml` (`docling-graph>=1.5.1`).

**Alternatives considered**:

- Keep custom NetworkX builder — rejected (duplicates docling-graph; misses footnote/cross-ref fidelity goals)
- Neo4j native store — deferred (GraphML + manifest sufficient for local/benchmark)

**Implementation approach**:

1. Build intermediate `DoclingDocument` or use docling-graph mapper input adapter from `ParsedDocument` sections/tables/footnotes (bridge layer in `docling_graph_mapper.py`).
2. Map docling-graph entity types → `GraphNodeType` / `GraphEdgeType` per [contracts/edge-catalog.md](./contracts/edge-catalog.md).
3. Post-process: inject XBRL fact nodes from `xbrl-facts-*` tables (all instances from `consolidate_xbrl_fact_rows` list output) under `doc-{accession}-xbrl-facts` section — docling-graph may not emit numeric XBRL contexts natively from our parse shape.

## R2: XBRL fact nodes — no cap

**Decision**: Materialize **every** `(concept, period, value)` instance from parsed XBRL tables; remove graph-stage `select_facts_for_index(..., max_facts=400)` truncation.

**Rationale**: Clarification session 2026-05-21 (no cap). Prior bug: dict consolidation dropped period contexts; fixed in `parsing/xbrl_facts.py` to list-of-instances — graph layer must consume full list.

**Alternatives considered**:

- Prioritized cap with audit exclusion — rejected by user
- Sample facts for graph size — rejected

## R3: Hybrid semantic similarity

**Decision**:

| Link method | Mechanism | v1 default |
|-------------|-----------|------------|
| `deterministic` | Match `xbrl_concept` QName + compatible fiscal period across filings | **ON** |
| `thematic` | Embedding cosine similarity on paragraph/section text; risk keyword bucket | **OFF** in CI; config threshold in `configs/graph_similarity.yaml` |

**Rationale**: Clarification B (hybrid). Deterministic links satisfy cross-period revenue questions without embedding infra in CI.

**Alternatives considered**:

- Embeddings only — rejected (hard to audit; violates financial grounding preference)
- No similarity edges v1 — rejected (spec FR-008)

**Thematic provider** (when enabled): prefer local embedding via existing stack (e.g. `sentence-transformers` all-MiniLM) behind `USE_THEMATIC_GRAPH_LINKS=1`; if dep too heavy, defer thematic to Phase 2 task with mock disabled in CI.

## R4: Reachability audit

**Decision**: BFS shortest path from `doc-{accession}` to each sampled evidence node using only structural edge types; hop budget **N=6**; pass threshold **≥95%**; stratified sample **≥100** facts (XBRL nodes + table rows with numeric cells).

**Rationale**: Clarifications on structural-only paths, sample population, N, and pass rate.

**Alternatives considered**:

- Include TEMPORAL_TRANSITION in audit — rejected (cross-filing navigation, not within-document grounding proof)
- Fixed 50-fact panel — superseded by ≥100 stratified sample

**Stratification** (planning default): proportional by form type (10-K vs 10-Q) and by node kind (60% XBRL fact / 40% table row).

## R5: Fail-closed materialization

**Decision**: Per-filing validation before adding to published snapshot:

- REJECT if: zero sections under document, any evidence node without CONTAIN path to document root, mandatory footnote target missing AND policy marks filing invalid (configurable strictness on footnotes: **warn** vs **fail** — default **warn**, fail only on zero sections / orphans).

**Rationale**: FR-011; 003 already allows partial corpus with excluded members.

## R6: Migration / parity

**Decision**: Golden parity suite on fixture AAPL accessions:

- Node counts within ±5% for sections/tables/rows
- 100% of legacy XBRL fact nodes have deterministic counterpart in new graph (by concept+period key)
- All table rows in legacy have CONTAIN path in new graph

**Rationale**: User directive #7; reduces cutover risk.

**Cutover**: Feature flag `GRAPH_BUILDER=docling-graph` default true after parity green; `legacy` flag for one release.

## R7: ParsedDocument bridge (docling-graph input)

**Decision**: Phase 1 does **not** re-parse raw XBRL in graph layer. Mapper consumes existing `ParsedDocument` JSON:

- Structural hierarchy via docling-graph **adapter** that reconstructs minimal Docling-like tree from sections/tables OR maps directly when docling-graph accepts custom graph build from tables.

**Open item for implement**: Verify docling-graph 1.5.x API for programmatic graph build without re-running Docling parse — if API requires `DoclingDocument`, add `parsing/docling_export.py` helper (still parsing layer, not ingestion).

**Fallback**: Direct mapping from `ParsedDocument` fields (current builder logic) validated against docling-graph schema in tests — satisfies “docling-graph as engine” via shared schema contract even if bridge is thin.

## References

- [001 research R3](../001-sec-disclosure-rag/research.md)
- [002 research-xbrl-retrieval](../002-live-disclosure-cli/research-xbrl-retrieval.md)
- [docling-graph](https://github.com/docling-project/docling-graph)
