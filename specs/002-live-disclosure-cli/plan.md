# Implementation Plan: Live Regulatory Disclosure Ingestion & Developer CLI

**Branch**: `002-live-disclosure-cli` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature spec plus workspace directives: `sec-api` via `uv`, `SEC_API_KEY` in `.env`, `src/ingestion/` live XBRL layer, unified `agent-query` CLI at `src/cli/main.py`.

**Builds on**: `001-sec-disclosure-rag` (Docling parse, docling-graph, LangGraph retrieval, MLflow, evaluation).

## Summary

Extend the financial GraphRAG platform with a **live XBRL ingestion layer** powered by the **`sec-api`** Python SDK (authenticated via `SEC_API_KEY`), a **versioned local download cache** under `data/raw/sec_downloads/`, and a unified **`agent-query`** CLI that orchestrates fetch → parse → graph → agentic retrieval → MLflow trace → terminal answer. Existing parsing, graph, retrieval, and evaluation packages from `001` are reused via public contracts; this feature adds `src/ingestion/` and `src/cli/` only.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + committed `uv.lock`

**New dependencies** (to add via `uv add sec-api`):
- `sec-api` — SEC EDGAR query, filing resolution, XBRL/download APIs ([sec-api.io](https://sec-api.io))

**Existing dependencies** (unchanged from `001`): `docling`, `docling-graph`, `langchain`, `langgraph`, `langchain-openai`, `mlflow`, `pydantic`, `networkx`, `httpx`, etc.

**Environment variables** (required for live fetch):
| Variable | Required | Purpose |
|----------|----------|---------|
| `SEC_API_KEY` | **Yes** (live fetch) | sec-api.io authentication |
| `LM_STUDIO_BASE_URL` | Yes (query mode) | Local Qwen endpoint |
| `LM_STUDIO_MODEL` | Yes (query mode) | Model id |
| `MLFLOW_TRACKING_URI` | Optional | Default `./mlruns` |
| `GOOGLE_API_KEY` | Optional | Benchmark judge only |

**Storage layout** (additive):
```text
data/raw/sec_downloads/{ticker}/{accession_number}/   # Phase 1A live XBRL pool
  ├── manifest.json                                   # artifact list + hashes
  ├── *.xml / *.xsd / *_cal.xml ...                   # raw XBRL package
data/raw/edgar/{cik}/{accession}/                     # legacy path (001); migrate readers
data/parsed/{issuer}/                                 # Docling output (001)
data/graphs/{issuer_id}/                              # GraphML snapshots (001)
data/cache/sec-api/                                   # ticker→CIK mapping cache
```

**Testing**: `pytest` with `SEC_API_KEY` skipped in CI (mock sec-api responses); contract tests for ingestion→parsing boundary

**Target platform**: Developer workstation with sec-api.io account + LM Studio for live query mode

**Performance goals**:
- Filing resolution + XBRL download: &lt; 30 s p95 per 10-K package (network-bound)
- Cache hit: ≥50% faster end-to-end vs cold fetch (spec SC-003)
- `agent-query ask`: &lt; 180 s p95 including graph build + local LLM (quality-first)

**Constraints**:
- Constitution: ingestion MUST NOT build graphs, run agents, or score benchmarks
- `SEC_API_KEY` MUST NOT be committed; fail fast at startup if missing in live modes
- CLI orchestrates layers only through `QueryService`, `GraphQueryAPI`, and ingestion public APIs
- All dependency changes via `uv add` / `uv lock` only

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Live artifacts hashed; parser fail-closed; CLI uses existing synthesis path |
| **II. Structural Semantics Preservation** | PASS | Raw XBRL → existing Docling pipeline unchanged |
| **III. Traceability** | PASS | `agent-query ask` reuses MLflow + `TrajectoryRecord` from `001` |
| **IV. Separation of Concerns** | PASS | `ingestion/` fetch only; `cli/` orchestrates; no judge in CLI hot path |
| **V. Code Health & Environment Stability** | PASS | Pydantic manifests; `uv.lock` bump; typed `SEC_API_KEY` guard |
| **VI. Rigorous Agent Evaluation** | PASS | `agent-query test` mode defers to existing `evaluation/` package |

**Post-design re-check**: `contracts/ingestion-boundary.md` defines ingestion→parsing handoff; CLI does not import `retrieval.orchestration` internals.

## Project Structure

### Documentation (this feature)

```text
specs/002-live-disclosure-cli/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md                    # /speckit-tasks (next)
```

### Source code (repository root — additive)

```text
src/
├── ingestion/                  # NEW — Phase 1A live XBRL
│   ├── __init__.py
│   ├── sec_client.py           # sec-api wrapper (ticker/CIK/accession → filings)
│   ├── xbrl_downloader.py      # manifest + .xml/.xsd download
│   ├── cache_manager.py        # hash, atomic writes, cache hit/miss
│   ├── validators.py           # XBRL package completeness
│   └── settings.py             # SEC_API_KEY, rate limits
├── cli/                        # NEW — Phase 5 unified CLI
│   ├── __init__.py
│   ├── main.py                 # Typer/argparse entry: agent-query
│   ├── commands/
│   │   ├── ask.py              # Live query orchestration
│   │   └── test.py             # CI graph-consistency smoke
│   └── pipeline.py             # fetch → parse → graph → query facade
├── parsing/                    # EXISTING — extend read path for sec_downloads
├── graph/                      # EXISTING
├── retrieval/                  # EXISTING
├── tracing/                    # EXISTING
└── evaluation/                 # EXISTING
```

**pyproject.toml updates**:
```toml
dependencies = [ ..., "sec-api>=1.0.36", ... ]

[project.scripts]
agent-query = "cli.main:app"    # uv run agent-query ...
# retain sec-* scripts for granular debugging
```

## Execution Phases (Unified Roadmap)

### Phase 0: Environment & Token Extraction Hook (Updated)

| Step | Action |
|------|--------|
| P0.1 | `uv add sec-api` → commit `uv.lock` |
| P0.2 | Add `SEC_API_KEY=` to `.env.example`; document in README |
| P0.3 | Implement `src/ingestion/settings.py`: load key via `os.environ` / `pydantic-settings`; raise `ConfigurationError` if missing when live mode requested |
| P0.4 | Factory `get_sec_client()` returning configured `sec_api` SDK handle (no key in logs) |
| P0.5 | CI: mock `SEC_API_KEY` for unit tests; skip live integration without secret |

**Deliverable**: `from ingestion.settings import require_sec_api_key` usable across ingestion modules.

### Phase 1A: Live XBRL Data Ingestion Layer (NEW)

| Step | Action |
|------|--------|
| P1A.1 | `sec_client.py`: map ticker → CIK (sec-api mapping + local cache file) |
| P1A.2 | Resolve latest or specified 10-K/10-Q by CIK, ticker, or accession |
| P1A.3 | `xbrl_downloader.py`: use sec-api Download / XBRL APIs to list `.xml`, `.xsd`, linkbase files |
| P1A.4 | Write artifacts to `data/raw/sec_downloads/{ticker}/{accession}/` with `manifest.json` |
| P1A.5 | `cache_manager.py`: content-hash dedup, atomic temp-dir writes, `--force-refresh` support |
| P1A.6 | `validators.py`: instance + taxonomy presence checks before `parse_ready=true` |
| P1A.7 | Public API: `ingestion.fetch_filing(identifier, form, force=False) -> CacheEntry` |

**Deliverable**: Programmatic fetch populates verified storage pools feeding Docling.

### Phase 1B: Parsing & Graph (EXISTING — path adapter)

| Step | Action |
|------|--------|
| P1B.1 | Extend `parsing/docling_pipeline.py` to accept primary input from `sec_downloads/.../instance.xml` (or bundled HTML if API returns it) |
| P1B.2 | `graph.cli build` reads parsed JSON from issuer keyed by ticker/CIK |
| P1B.3 | Contract test: `ingestion` output → `parsing` → `graph` without cross-import violations |

**Deliverable**: Same graph quality as `001` but sourced from live cache paths.

### Phase 2: Agentic Retrieval (EXISTING)

Reuse `retrieval/orchestration/` LangGraph macro → meso → micro → synthesize unchanged.

### Phase 3: MLflow Tracing (EXISTING)

Reuse `tracing/mlflow_langgraph.py`; CLI passes run metadata (`ticker`, `accession`, `snapshot_id`).

### Phase 4: Evaluation (EXISTING)

`agent-query test` invokes registry specs + optional benchmark subset; no duplication of judge logic.

### Phase 5: Developer CLI — `agent-query` (NEW)

| Step | Action |
|------|--------|
| P5.1 | `src/cli/main.py` Typer app with subcommands `ask` and `test` |
| P5.2 | **`ask` mode**: `--ticker` / `--cik` / `--accession`, `--query`, `--form`, `--force-refresh`, `--snapshot-id` |
| P5.3 | Orchestration in `cli/pipeline.py`: Phase 1A → 1B → graph build → `QueryService.answer()` → stdout JSON/human |
| P5.4 | **`test` mode**: fetch on-demand filing(s), build graph, assert node/edge counts vs registry thresholds |
| P5.5 | Register `[project.scripts] agent-query = "cli.main:app"` |
| P5.6 | Rich/plain terminal output: answer, citations, filings used, `mlflow_run_id` |

**Example**:
```bash
export SEC_API_KEY=...
uv run agent-query ask \
  --ticker AAPL \
  --query "Examine lease obligations footnote changes between Q2 and Q3"
```

**Deliverable**: Single command live path from ticker to grounded answer.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New `ingestion/` package (5th top-level module) | User-mandated live layer distinct from Docling parse | Collapsing into `parsing/` blurs fetch vs parse responsibilities and complicates contract tests |
| `sec-api` paid API dependency | Reliable XBRL artifact discovery vs scraping EDGAR HTML | Raw `requests` EDGAR scraping is brittle and violates SEC fair-access patterns at scale |

## Integration with `001-sec-disclosure-rag`

| `001` component | `002` interaction |
|-----------------|-------------------|
| `parsing/docling_pipeline.py` | New input root: `sec_downloads/` |
| `graph/builder.py` | Unchanged |
| `retrieval/service.py` | Called by CLI `pipeline.py` |
| `evaluation/runner.py` | Optional `agent-query test --benchmark pilot` |
| `sec-ingest` / `sec-query` CLIs | Retained for debugging; `agent-query` is primary UX |
