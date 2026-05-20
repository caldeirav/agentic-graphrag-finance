# Implementation Plan: Docling-Graph Knowledge Materialization

**Branch**: `004-docling-graph-materialization` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)

**Input**: Extend **003** multi-filing corpus materialization: replace `src/graph/builder.py` custom mapper with **docling-graph** as sole `GraphSnapshot` engine. Preserve XBRL-primary `ParsedDocument` inputs only; do not change ingestion or parsing contracts.

**Builds on**: `003-multi-filing-corpus` (`graph/registry.py`, `agent-query materialize`), `002-live-disclosure-cli` (parse/cache, [research-xbrl-retrieval.md](../002-live-disclosure-cli/research-xbrl-retrieval.md)), `001-sec-disclosure-rag` (docling-graph research R3, GraphML store, LangGraph retrieval).

## Summary

Replace the hand-rolled `build_snapshot()` graph mapper with a **docling-graph**-driven materialization pipeline that emits the full **edge type catalog** (structural + temporal + hybrid semantic similarity), materializes **every** XBRL fact instance (all period contexts), enforces **fail-closed** per-filing publish rules, and adds a **reachability audit** command (≥100 stratified facts, structural paths only, N=6, 95% gate). Integrate audit metadata into **003** snapshot manifests and MLflow trajectories without changing ingestion or parsing boundaries.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Primary dependencies** (existing): `docling`, `docling-graph>=1.5.1`, `networkx`, `pydantic` — no new runtime deps required for deterministic similarity; optional `sentence-transformers` or existing LM embedding path gated by config for thematic links (see [research.md](./research.md)).

**Reuse (003 / 002 / 001 — no replacement)**:

| Module | Role |
|--------|------|
| `ingestion.fetch_filing`, `ingestion.corpus` | Unchanged; corpus still N × fetch |
| `parsing.sec_download_adapter.parse_from_cache` | Sole input to graph layer |
| `graph.store.save_snapshot` / `load_snapshot` | GraphML persistence unchanged |
| `graph.registry.build_issuer_snapshot` | Extend: call new mapper + attach audit report |
| `cli.corpus_pipeline.run_materialize_pipeline` | Wire audit gate before “ready” status |
| `graph.query_api.LocalGraphQueryAPI` | Extend: shortest-path for audit |
| `retrieval.*` | Trajectory edge-type logging only (no graph build imports) |

**New / refactored modules**:

| Module | Role |
|--------|------|
| `graph/docling_graph_mapper.py` | docling-graph ER → `GraphNode` / `GraphEdge` |
| `graph/legacy_builder.py` | Renamed from current `builder.py`; parity tests only |
| `graph/builder.py` | Thin facade: `build_snapshot()` → docling-graph mapper |
| `graph/similarity.py` | Deterministic concept links + optional thematic linker |
| `graph/reachability.py` | Stratified audit, JSON report, pass/fail gate |
| `graph/edge_catalog.py` | Canonical type list + traversal policy constants |
| `cli/commands/graph_audit.py` | `agent-query graph-audit --snapshot-id …` |
| `models/graph_audit.py` | `ReachabilityAuditReport`, `FilingMaterializationResult` |

**Storage layout** (extend 003):

```text
data/graphs/{issuer}/
  ├── index.json
  ├── {snapshot_id}.graphml
  ├── {snapshot_id}.manifest.json      # + audit_summary, builder_version
  └── {snapshot_id}.reachability.json  # NEW: audit artifact
```

**Testing**: `pytest` — parity tests (legacy vs docling-graph on fixture AAPL), reachability audit contract tests, fail-closed materialization cases, contract import boundaries.

**Performance goals**:

- Default 5-filing issuer materialize: graph build < 3 min p90 incremental over current baseline (SC stretch; large XBRL fact sets accepted)
- Reachability audit on warm snapshot: < 60 s for 100-sample panel
- Single-filing graph build: < 90 s p90 on fixture 10-Q

**Constraints**:

- **No ingestion/parsing contract changes**
- **No per-filing XBRL fact cap** — remove `select_facts_for_index` cap at graph boundary
- **Structural-only** paths for 95% gate; similarity/temporal excluded from audit
- **Fail-closed** per filing; partial corpus snapshot allowed (003 pattern)
- docling-graph is **default** publish path after parity window

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | All nodes trace to `ParsedDocument` + filing accession; audit proves structural reachability; fail-closed on broken graphs |
| **II. Structural Semantics Preservation** | PASS | docling-graph hierarchy + FOOTNOTE_OF/REFERENCES; XBRL facts as first-class nodes; no flat-string index |
| **III. Traceability** | PASS | Trajectory logs edge types on paths; `reachability.json` + MLflow artifact; snapshot manifest audit fields |
| **IV. Separation of Concerns** | PASS | Graph layer only consumes `ParsedDocument`; ingestion/parsing unchanged; retrieval does not build graphs |
| **V. Code Health & Environment Stability** | PASS | Pydantic audit models; `uv.lock`; optional thematic deps behind config flag |
| **VI. Rigorous Agent Evaluation** | PASS | Reachability audit as release gate; benchmark can assert manifest `audit_pass_rate` |

**Post-design re-check**: Contracts in [contracts/](./contracts/) enforce layer boundary and audit edge whitelist; no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/004-docling-graph-materialization/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── edge-catalog.md
│   ├── graph-materialize-boundary.md
│   └── reachability-audit.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source (repository root)

```text
src/
├── graph/
│   ├── builder.py              # Facade → docling_graph_mapper
│   ├── legacy_builder.py       # Parity only (rename from current builder)
│   ├── docling_graph_mapper.py # NEW
│   ├── edge_catalog.py         # NEW
│   ├── similarity.py           # NEW
│   ├── reachability.py         # NEW
│   ├── registry.py             # Extend audit + manifest
│   ├── query_api.py            # Structural shortest path
│   └── store.py                # Unchanged
├── models/
│   ├── enums.py                # + CHUNK_XBRL_FACT, SEMANTIC_SIMILARITY
│   └── graph_audit.py          # NEW
├── cli/
│   ├── corpus_pipeline.py      # Wire audit after build
│   └── commands/graph_audit.py # NEW
└── retrieval/
    └── tracing/                # Edge types on citation paths

tests/
├── unit/test_edge_catalog.py
├── unit/test_reachability.py
├── unit/test_similarity_deterministic.py
├── integration/test_graph_builder_parity.py
└── contract/test_graph_materialize_boundary.py

configs/
├── graph_audit.yaml            # hop_budget, sample_size, pass_threshold, seed
└── graph_similarity.yaml       # thematic threshold, enable flag
```

**Structure Decision**: Extend existing `src/graph/` and 003 CLI materialize path; no new top-level package.

## Complexity Tracking

No constitution violations requiring justification.

## Phase 0: Research

**Status**: Complete → [research.md](./research.md)

Resolved:

- docling-graph as sole mapper with `ParsedDocument` bridge (R1, R7)
- No XBRL cap at graph boundary (R2)
- Hybrid similarity: deterministic ON, thematic config-gated (R3)
- Reachability audit parameters (R4)
- Fail-closed rules (R5)
- Legacy parity then cutover (R6)

## Phase 1: Design & Contracts

**Status**: Complete

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Edge catalog contract | [contracts/edge-catalog.md](./contracts/edge-catalog.md) |
| Materialize boundary | [contracts/graph-materialize-boundary.md](./contracts/graph-materialize-boundary.md) |
| Reachability audit | [contracts/reachability-audit.md](./contracts/reachability-audit.md) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Phase 2: Implementation Outline (for tasks.md)

### P2.1 Edge catalog & models

- Add `GraphEdgeType.SEMANTIC_SIMILARITY`, `GraphNodeType.CHUNK_XBRL_FACT`
- Implement `graph/edge_catalog.py` as single source for audit whitelist and agent policy
- Pydantic models: `ReachabilityAuditReport`, `AuditEntry`, `FilingMaterializationResult`

### P2.2 Docling-graph mapper

- `docling_graph_mapper.map_filing(ParsedDocument) -> (nodes, edges, FilingMaterializationResult)`
- Map docling-graph entities → catalog types (CONTAIN, NEXT, FOOTNOTE_OF, REFERENCES)
- Inject all XBRL instances from `consolidate_xbrl_fact_rows` list under `{doc}-xbrl-facts`
- Fail-closed: zero sections, orphan evidence without CONTAIN chain
- `builder.build_snapshot()` delegates here; version `docling-graph-mapper-1.0.0`

### P2.3 Issuer-level passes (003 registry)

- `similarity.add_deterministic_concept_edges(snapshot)` across filings
- `similarity.add_thematic_edges(snapshot, config)` when `USE_THEMATIC_GRAPH_LINKS=1`
- `builder.add_temporal_transitions(snapshot, corpus_definition)` — preserve 003 ordering
- `registry.build_issuer_snapshot(..., run_audit=True)` saves manifest + reachability artifact

### P2.4 Reachability audit

- `reachability.audit_snapshot_reachability()` — stratified sample ≥100, BFS N=6, structural only
- CLI `graph-audit` command; hook into `materialize` pipeline
- Manifest fields: `audit_ready`, `audit_pass_rate`, `reachability_artifact`

### P2.5 Retrieval integration

- `query_api.shortest_structural_path(from_doc, to_node)`
- MLflow: log `reachability.json`; trajectory records `path_edge_types` on citations

### P2.6 Migration

- Rename current `builder.py` → `legacy_builder.py`
- `tests/integration/test_graph_builder_parity.py` on AAPL fixtures (±5% structural counts, 100% XBRL key coverage)
- Default `GRAPH_BUILDER=docling-graph`; remove legacy default after green CI

## Phase 3–5 (deferred to tasks / implement)

- **Phase 3**: Unit + contract tests per module
- **Phase 4**: Integration materialize → audit → ask trajectory
- **Phase 5**: Docs, README quickstart link, CI graph-audit on fixtures

## Dependencies & References

- [003 spec](../003-multi-filing-corpus/spec.md) — corpus manifests, `index.json`, immutability
- [002 research-xbrl-retrieval](../002-live-disclosure-cli/research-xbrl-retrieval.md) — XBRL fact identity, period contexts
- [001 research R3](../001-sec-disclosure-rag/research.md) — docling-graph rationale
- Current mapper: `src/graph/builder.py` (`GRAPH_BUILDER_VERSION`)

## Stop Condition

Planning stops after Phase 2 outline. Next command: **`/speckit-tasks`** to generate `tasks.md`, then **`/speckit-implement`**.
