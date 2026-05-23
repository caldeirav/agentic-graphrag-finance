# Research: Graph-Native Meso and Micro Navigation (009)

**Branch**: `009-graph-native-meso-micro` | **Date**: 2026-05-23

## R1 — Navigation control model

**Decision**: LLM proposes next hop (or ≤3 candidates); deterministic validator approves before `NavigationVisit` is recorded (same pattern as 008 macro).

**Rationale**: Clarification Q1; constitution III requires auditable per-step decisions; validator enforces structural-only edges and macro scope without trusting LLM graph knowledge.

**Alternatives considered**:
- Pure BFS/beam without LLM — rejected: loses query-conditioned ranking and agentic plan narrative in trajectory.
- Full-path upfront planning — rejected: brittle on dead ends and incomplete graphs; harder to trace partial failures.

## R2 — Agent-allowed edge types

**Decision**: `STRUCTURAL_EDGE_TYPES` only (`CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`). Narrow `AGENT_TRAVERSAL_POLICY` in `graph/edge_catalog.py` to match (remove `TEMPORAL_TRANSITION` and `SEMANTIC_SIMILARITY` from agent policy).

**Rationale**: Clarification Q2; multi-filing handled by macro binding + per-filing document roots, not cross-filing graph hops.

**Alternatives considered**:
- Keep temporal edges for meso — rejected: duplicates macro scope and weakens trace explainability.
- Semantic similarity for micro — rejected: non-structural hops fail SC-004 path rubrics and constitution II.

## R3 — Full-graph scan metric (SC-003)

**Decision**: `scan_ratio = visited_navigable_nodes / total_navigable_nodes` within macro-bound filing set; **full scan** when `scan_ratio ≥ 0.90` before required chunk retrieved.

**Rationale**: Clarification Q3; aligns with reachability audit node universe (sections + chunk node types).

**Navigable node definition**: `SECTION`, `CHUNK_TABLE`, `CHUNK_ROW`, `CHUNK_PARAGRAPH`, `CHUNK_XBRL_FACT` nodes whose document root accession is in `filing_set`.

## R4 — Heuristic fallback

**Decision**: No production fallback. Empty micro set → `INSUFFICIENT_EVIDENCE` or fail-closed with partial `navigation_trace` persisted.

**Rationale**: Clarification Q4; FR-013/FR-013a. Existing `score_section` / `score_chunk` may remain **inside** validator scoring of LLM candidates, not as a parallel retrieval path.

## R5 — Meso → micro handoff

**Decision**: Top **3** sections per bound filing by meso rank score; micro runs independently per section root.

**Rationale**: Clarification Q5; caps fan-out on YoY (2 filings × 3 sections = 6 micro roots max).

## R6 — Navigation budgets (planning defaults)

**Decision**: `configs/graph_navigation.yaml`:

| Key | Default | Scope |
|-----|---------|--------|
| `meso.max_hops_per_filing` | 24 | Section discovery per document root |
| `meso.max_visits_per_filing` | 80 | Distinct nodes visited in meso |
| `micro.max_hops_per_section` | 12 | From section root |
| `micro.max_visits_per_section` | 40 | Distinct nodes per section |
| `query.max_total_visits` | 200 | Meso + micro combined |
| `llm.max_candidates_per_proposal` | 3 | Validator picks one approved hop |

**Rationale**: FR-007; conservative defaults on AAPL multi-filing snapshot (~500–2k navigable nodes). Tunable without spec change.

**Alternatives considered**:
- Single global hop cap only — rejected: micro starves when meso explores widely.

## R7 — Graph API extensions

**Decision**: Extend `GraphQueryAPI` / `LocalGraphQueryAPI` with:
- `document_roots_for_filings(snapshot_id, filings) -> list[GraphNode]`
- `outgoing_edges(snapshot_id, node_id, edge_types) -> list[GraphEdge]` (typed, for trace)
- `navigable_node_count(snapshot_id, filings) -> int` (eval harness)

Reuse existing `neighbors()` for candidate enumeration; validator uses `outgoing_edges` for edge-type proof.

## R8 — Gold-path eval corpus

**Decision**: `tests/fixtures/gold_path/` (committed JSONL + manifest) mirroring `aapl_macro_snapshot`; optional runtime copy under `data/benchmarks/finagentbench/gold_path.jsonl` (gitignored) for local expansion. CI uses fixtures only.

**Rationale**: `data/` gitignored; 008 pattern uses fixtures for CI + generator script. Minimum 40 items; target 50 at task time.

**Label fields**: `query`, `expected_macro_accessions`, `required_chunk_node_ids`, `acceptable_edge_sequences`, `multi_filing_required`.

## R9 — Mock LLM for CI

**Decision**: `USE_MOCK_LLM=1` serves hop fixtures from `tests/fixtures/navigation_planner/{meso,micro}/*.json` keyed by query hash or scenario id; validator always runs real code.

**Rationale**: Same as 008; gold-path gate in CI without LM Studio.

## R10 — XBRL fact nodes in micro traversal

**Decision**: `CHUNK_XBRL_FACT` nodes are valid micro targets and navigable nodes; reached via `CONTAINS` from section/table context only (no invented edges).

**Rationale**: Existing micro_extractor already scores XBRL facts; graph-native path must support numeric queries without semantic edges.
