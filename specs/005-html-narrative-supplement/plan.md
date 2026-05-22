# Implementation Plan: Supplementary SEC HTML Narrative Ingestion

**Branch**: `005-html-narrative-supplement` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)

**Input**: Extend **002/003/004** pipeline: supplementary HTML narrative (MD&A, risk factors, business description) for accessions with cached XBRL; merged `ParsedDocument`; source-tagged graph nodes; **LLM intent router** with keyword fallback and **MLflow-backed router trace** (FR-013–016).

**Builds on**: `004-docling-graph-materialization` (graph mapper, reachability), `003-multi-filing-corpus` (materialize, snapshots), `002-live-disclosure-cli` (EDGAR XBRL cache, `FILING_HTML` role).

## Summary

Add a **supplementary HTML narrative path** that (1) resolves narrative HTML from inline/iXBRL in the cached XBRL package with optional `.htm` fallback, (2) parses Item 1 / 1A / 7 (and equivalents) into `SectionBlock`s tagged `source_type=HTML`, (3) **merges** into the existing per-accession `ParsedDocument` without altering XBRL-primary fields, (4) materializes HTML chunks on the **same** issuer snapshot with `source_type` on graph node properties, and (5) introduces an **`intent_router`** LangGraph node that classifies `numeric | qualitative | hybrid`, applies source-biased ranking in `micro_extractor`, and persists a typed **`IntentRouterTrace`** on `TrajectoryRecord` plus MLflow params/artifact before micro-extraction.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Primary dependencies** (existing): `docling`, `docling-graph`, `langgraph`, `langchain`, `httpx`, `pydantic`, `mlflow` — optional v1 add: `beautifulsoup4` for robust HTML section boundaries (see [research.md](./research.md); stdlib `html.parser` acceptable if fixture tests pass).

**Reuse (unchanged boundaries)**:

| Module | Role |
|--------|------|
| `ingestion.edgar_xbrl` | XBRL package download; extend with narrative artifact resolution |
| `ingestion.fetch_filing` / `cache_manager` | Cache entry + manifest; add HTML roles |
| `parsing.docling_xbrl` / `sec_download_adapter` | XBRL-primary parse; call HTML merge after XBRL |
| `graph.docling_graph_mapper` | Extend node `properties["source_type"]` |
| `graph.registry` / `corpus_pipeline` | Default HTML narrative on materialize |
| `retrieval.orchestration` | Insert `intent_router`; bias `micro_extractor` |
| `tracing.mlflow_langgraph` | Router trace → trajectory + `intent_router.json` |

**New / refactored modules**:

| Module | Role |
|--------|------|
| `ingestion/html_narrative.py` | Resolve inline vs fallback `.htm`; paired ingest gate |
| `parsing/html_narrative.py` | Section extract (MD&A, risk, business); merge into `ParsedDocument` |
| `models/enums.py` | `EvidenceSourceType`, `QueryIntent`, `IntentSource`, `SourceBias`, `RouterFallbackReason` |
| `models/query.py` | `IntentRouterTrace`; extend `EvidenceChunk` with `source_type` |
| `retrieval/orchestration/nodes/intent_router.py` | LLM classify + keyword fallback |
| `retrieval/orchestration/nodes/micro_extractor.py` | Source-biased scoring from `intent_trace` |
| `retrieval/orchestration/graph.py` | `macro → intent_router → meso → micro → synthesize` |
| `configs/html_narrative.yaml` | Section heading patterns, opt-out defaults |
| `configs/intent_router.yaml` | LLM prompt, keyword fallback lexicon, timeouts |

**Storage layout** (extend 002):

```text
data/raw/sec_downloads/{ticker}/{accession}/
  ├── manifest.json                    # + html_artifact_path, html_status
  ├── *_htm.xml                        # XBRL instance (existing)
  └── filing.htm                       # optional fallback narrative

data/parsed/{ticker}/{accession}.json  # merged ParsedDocument (XBRL + HTML sections)

data/graphs/{issuer}/{snapshot_id}.*   # nodes carry properties.source_type
```

**Testing**: `pytest` — HTML section fixtures, merge idempotency, intent router unit (LLM mock + keyword fallback), trajectory contract (FR-013–016), integration ask with HTML citation on qualitative item.

**Performance goals**:

- Supplementary HTML parse per filing: < 30 s p90 on pilot 10-K (inline HTML)
- Intent router: < 5 s p90 (local LLM); keyword fallback < 50 ms
- Materialize with HTML default: < 2× XBRL-only p90 on 5-filing corpus (stretch)

**Constraints**:

- **XBRL-primary** for numeric facts (constitution II); HTML never replaces instance parse
- **No HTML-only ingest** without cached XBRL package (FR-001)
- **Single** `ParsedDocument` per accession (FR-003b)
- Intent router trace is **canonical** for `query_intent`; macro `intent_summary` must not overwrite it (edge case)
- Router failure **must not** fail ask (keyword fallback)

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | HTML excerpts cite graph nodes tied to filing accession; no invented prose; fail-closed HTML parse per filing without breaking XBRL |
| **II. Structural Semantics Preservation** | PASS | XBRL tables/facts unchanged; HTML as labeled `SectionBlock`s; graph hierarchy preserved |
| **III. Traceability** | PASS | `IntentRouterTrace` on `TrajectoryRecord`; MLflow params + `intent_router.json`; citations carry `source_type`; eval reads trajectory |
| **IV. Separation of Concerns** | PASS | Ingest → parse → graph → retrieval; router lives in `retrieval/orchestration/`; no parse in graph layer |
| **V. Code Health & Environment Stability** | PASS | Pydantic enums/models at boundaries; `uv.lock`; contract tests for trajectory fields |
| **VI. Rigorous Agent Evaluation** | PASS | Benchmark asserts HTML citation + router fields (SC-006/007); judge can score trajectory fidelity |

**Post-design re-check**: Contracts in [contracts/](./contracts/) define layer boundaries and trajectory schema; no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-html-narrative-supplement/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── html-narrative-ingest.md
│   ├── parsed-document-merge.md
│   ├── intent-router-trace.md
│   └── source-tagged-citations.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source (repository root)

```text
src/
├── ingestion/
│   ├── html_narrative.py       # NEW
│   ├── edgar_xbrl.py           # + inline HTML path helper
│   └── package_utils.py        # + narrative artifact probe
├── parsing/
│   ├── html_narrative.py       # NEW
│   └── sec_download_adapter.py # merge hook after XBRL parse
├── models/
│   ├── enums.py                # + source/intent enums
│   ├── filing.py               # SectionBlock.source_type
│   └── query.py                # IntentRouterTrace, EvidenceChunk.source_type
├── graph/
│   └── docling_graph_mapper.py # properties.source_type on chunks
├── retrieval/
│   └── orchestration/
│       ├── graph.py            # + intent_router node
│       └── nodes/
│           ├── intent_router.py    # NEW
│           ├── meso_router.py      # optional HTML section boost
│           └── micro_extractor.py  # source bias
├── tracing/
│   └── mlflow_langgraph.py     # log router trace + params
└── cli/
    └── corpus_pipeline.py      # default HTML; --skip-html-narrative

tests/
├── unit/test_html_narrative.py
├── unit/test_intent_router.py
├── unit/test_intent_router_trace.py
└── integration/test_ask_html_citation.py

configs/
├── html_narrative.yaml
└── intent_router.yaml
```

## Phase 0: Research (complete → [research.md](./research.md))

Resolved: inline iXBRL HTML as primary narrative source; stdlib/BS4 section parser; intent router placement and fallback lexicon; trajectory field contract aligned with spec table.

## Phase 1: Design (complete)

- [data-model.md](./data-model.md) — entity extensions
- [contracts/](./contracts/) — ingest, parse merge, router trace, citations
- [quickstart.md](./quickstart.md) — operator validation

## Phase 2: Implementation outline (for `/speckit-tasks`)

| Phase | Scope | Depends |
|-------|--------|---------|
| **P1** | Models + enums + ingest `html_narrative` + manifest HTML status | — |
| **P2** | HTML parse + merge into `ParsedDocument` + unit tests | P1 |
| **P3** | Graph `source_type` on nodes + materialize default / opt-out | P2 |
| **P4** | `intent_router` node + keyword fallback + state wiring | — |
| **P5** | `micro_extractor` source bias + citation `source_type` in synthesis/CLI | P3, P4 |
| **P6** | MLflow router trace (FR-015) + trajectory contract tests | P4, P5 |
| **P7** | Integration qualitative benchmark smoke + quickstart validation | P6 |

## Complexity Tracking

> No constitution violations requiring justification.

| Item | Decision | Simpler alternative rejected |
|------|----------|------------------------------|
| New LangGraph node | `intent_router` between macro and meso | Overloading `macro_router` conflates temporal filing bind with evidence-source intent |
| Merged parse file | Single `ParsedDocument` JSON | Sidecar HTML parse complicates graph loader and violates FR-003b |
