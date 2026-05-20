# Implementation Plan: Multi-Filing Issuer Corpus & Temporal Snapshots

**Branch**: `003-multi-filing-corpus` | **Date**: 2026-05-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature spec + directive: **extend `002` ingestion/cache and existing graph snapshots** (no parallel fetch stack, no new UI).

**Builds on**: `002-live-disclosure-cli` (EDGAR ingest, `data/raw/sec_downloads/`, `agent-query ask`) and `001-sec-disclosure-rag` (Docling parse, multi-doc `build_snapshot`, LangGraph retrieval, MLflow).

## Summary

Add **issuer-level corpus orchestration** atop existing single-filing `fetch_filing` + `cache_manager`, materialize **multi-filing `GraphSnapshot`** versions under `data/graphs/{issuer}/` (builder already supports multiple `ParsedDocument`s and `TEMPORAL_TRANSITION` edges), and wire **temporal binding + snapshot scope transparency** through `agent-query` and benchmark contracts. Net-new code stays thin: ingestion listing/resolution, corpus materialization facade, temporal resolver, CLI pipeline refactor, retrieval state pre-binding, MLflow manifest artifacts.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Reuse (002 — no replacement)**:
- `ingestion.fetch_filing`, `cache_manager`, `validators`, `edgar_client` (extend with filing **list** API)
- `data/raw/sec_downloads/{ticker}/{accession}/` + per-filing `manifest.json`
- `parsing.sec_download_adapter.parse_from_cache`
- `graph.builder.build_snapshot` (multi-doc + temporal edges)
- `graph.store.save_snapshot` / `load_snapshot`
- `retrieval.service.QueryService`, MLflow tracing

**New / extended modules** (additive):

| Module | Role |
|--------|------|
| `ingestion/corpus.py` | Corpus definition, batch fetch orchestration, cap validation (FR-007a) |
| `ingestion/edgar_client.py` | `list_recent_filings()` from EDGAR `submissions.recent` |
| `models/corpus.py` | `CorpusDefinition`, `IssuerCorpus`, `FilingBinding`, `SnapshotScopeManifest` |
| `graph/registry.py` | Per-issuer snapshot index, resolve latest / by id, stale hints |
| `retrieval/temporal.py` | Fiscal-period binding (structured + NL via existing LLM path) |
| `cli/corpus_pipeline.py` | `materialize_corpus` + `run_ask_pipeline` multi-filing flow |
| `cli/commands/materialize.py` | Standalone corpus build (FR-016) |

**Storage layout** (additive):

```text
data/raw/sec_downloads/{ticker}/{accession}/     # unchanged (002)
data/parsed/{ticker}/{accession}.json            # one ParsedDocument per filing (extend naming)
data/graphs/{issuer_id}/
  ├── index.json                                 # NEW: snapshot version registry + filing summary
  ├── {snapshot_id}.graphml                      # existing
  └── {snapshot_id}.manifest.json                # existing GraphManifest
```

**Environment**: `EDGAR_USER_AGENT` (002 EDGAR path); `SEC_API_KEY` only if sec-api fallback enabled — primary path remains direct EDGAR per current tree.

**Testing**: `pytest` — unit tests for corpus list/cap/fiscal binding; integration with fixture multi-accession set under `tests/fixtures/sec_downloads/`; contract tests for manifest schema; benchmark binding assertions (FR-017).

**Performance goals** (from spec):
- Default 5-filing corpus cold materialize: &lt; 10 min p90 (SC-001)
- Cache-hit re-materialize: ≥50% faster (SC-002)
- Per-question binding only (no full re-build): &lt; 5 s p95 when snapshot warm

**Constraints**:
- **No new ingestion download protocol** — batch = N × existing `fetch_filing`
- **No graph schema rewrite** — extend manifest sidecars only
- Ingestion MUST NOT invoke `build_snapshot` or LangGraph (constitution IV)
- Immutability: new `snapshot_id` per membership change (FR-006)
- Default cap: 12 filings; overflow → reject (clarification B)

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Same XBRL cache path; binding manifest lists accessions; fail-closed on missing comparison periods |
| **II. Structural Semantics Preservation** | PASS | Reuse Docling/XBRL parse per filing; multi-doc graph preserves per-filing doc nodes |
| **III. Traceability** | PASS | `SnapshotScopeManifest` + `BindingManifestRecord` logged to MLflow; snapshot version on every ask |
| **IV. Separation of Concerns** | PASS | `ingestion/corpus.py` fetch-only; `graph/` build only; `retrieval/temporal.py` bind only; `cli/` orchestrates |
| **V. Code Health & Environment Stability** | PASS | Pydantic models in `models/corpus.py`; `uv.lock` unchanged unless new deps (none required) |
| **VI. Rigorous Agent Evaluation** | PASS | Benchmark contract adds structured `temporal_scope`; binding assertion hooks (FR-017) |

**Post-design re-check**: Contracts in `contracts/` keep ingestion→parsing→graph→retrieval boundaries; corpus orchestration does not import `retrieval.orchestration.nodes`.

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-filing-corpus/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── corpus-boundary.md
│   ├── temporal-scope.md
│   └── snapshot-scope-manifest.md
└── tasks.md             # /speckit-tasks (next)
```

### Source code (repository root — additive / extend)

```text
src/
├── ingestion/
│   ├── edgar_client.py          # EXTEND: list_recent_filings()
│   ├── corpus.py                # NEW: CorpusDefinition, materialize_members()
│   └── __init__.py              # export corpus APIs
├── models/
│   └── corpus.py                # NEW: corpus + manifest types
├── graph/
│   ├── builder.py               # EXISTING (multi-doc ready)
│   ├── store.py                 # EXISTING
│   └── registry.py              # NEW: index.json, latest, stale probe
├── retrieval/
│   └── temporal.py              # NEW: resolve_temporal_scope(), bind_filings()
├── cli/
│   ├── corpus_pipeline.py       # NEW: multi-filing materialize + ask
│   ├── pipeline.py              # REFACTOR: delegate to corpus_pipeline
│   └── commands/
│       ├── ask.py               # EXTEND: --period, --compare, snapshot scope output
│       └── materialize.py       # NEW: agent-query materialize
├── parsing/
│   └── sec_download_adapter.py  # EXTEND: per-accession parsed path helper
└── evaluation/                  # EXTEND: benchmark case temporal_scope field
```

**Structure decision**: Single Python package layout unchanged; feature adds orchestration in `ingestion/corpus.py` + `cli/corpus_pipeline.py` rather than a new top-level layer, honoring 002 boundaries.

## Execution Phases

### Phase 0: Research & contracts prep

- Confirm EDGAR `submissions.recent` supports listing last N 10-K/10-Q with `reportDate` for fiscal labeling ([research.md](./research.md))
- Finalize `SnapshotScopeManifest` JSON schema ([contracts/snapshot-scope-manifest.md](./contracts/snapshot-scope-manifest.md))

### Phase 1A: Ingestion corpus extension (002)

1. `list_recent_filings(cik, form_types, *, max_per_form)` — dedupe by fiscal period, prefer latest non-superseded
2. `CorpusDefinition` model — `default_trailing` | `explicit_accessions` | `date_range` with cap enforcement
3. `materialize_corpus_members()` — loop `fetch_filing`, aggregate `CorpusMaterializationJob` result
4. Fixture mode: synthetic multi-accession entries under `tests/fixtures/sec_downloads/{ticker}/`

### Phase 1B: Multi-filing graph snapshots (001 graph)

1. Parse each cache entry → `ParsedDocument` at `data/parsed/{ticker}/{accession}.json`
2. `build_snapshot(issuer, docs)` — reuse temporal edges (already in builder)
3. `graph/registry.py` — write `index.json`, immutable version entries, `get_latest_snapshot(issuer)`
4. Standalone CLI: `uv run agent-query materialize --ticker AAPL`

### Phase 2: Temporal binding & ask pipeline

1. `retrieval/temporal.py` — fiscal period labels from `FilingRef.period_end` + form type; structured benchmark scope; NL via macro LLM only when no pre-bind
2. Refactor `run_ask_pipeline`:
   - Load or materialize default snapshot (1×10-K + 4×10-Q)
   - `bind_filings_for_query()` → subset + optional extend snapshot
   - Pass `filing_set` + `binding_manifest` into `QueryService` metadata
3. Stale probe: compare registry vs `list_recent_filings`; set `stale_snapshot` on manifest (FR-012a)
4. `ask` output: **Snapshot scope** section (period, form, accession, stale warning)

### Phase 3: Retrieval & evaluation integration

1. `macro_router`: if `state["filing_set"]` pre-populated from binding, skip LLM filing selection
2. Benchmark registry: require `temporal_scope` object per case ([contracts/temporal-scope.md](./contracts/temporal-scope.md))
3. MLflow artifact: `binding_manifest.json` per run
4. Tests: SC-003 binding accuracy set (fixture issuers)

### Phase 4: Hardening

- Concurrent materialize lock file per issuer
- Partial member failure handling (exclude failed, block dependent queries)
- Update README + [quickstart.md](./quickstart.md)

## Complexity Tracking

No constitution violations requiring justification. Multi-filing orchestration is coordination only; graph builder and ingestion fetch remain unchanged in semantics.
