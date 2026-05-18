# Implementation Plan: Agentic SEC Disclosure Reasoning & Benchmarking

**Branch**: `001-sec-disclosure-rag` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-sec-disclosure-rag/spec.md` plus user tech-stack directives (uv, LangChain/LangGraph, LM Studio/Qwen, Docling, docling-graph, MLflow, Gemini judge).

## Summary

Build a four-layer financial GraphRAG system that ingests SEC 10-K/10-Q filings with layout-preserving Docling XBRL parsing, materializes hierarchical knowledge graphs via docling-graph, resolves ambiguous queries through a three-stage LangGraph router (macro → meso → micro) backed by a local Qwen model in LM Studio, logs full trajectories to MLflow with LangGraph integration, and benchmarks outcomes via a modular evaluation runner (FinDER, FinAgentBench, FinanceBench) scored by Gemini 2.5 Pro judges. Workspace reproducibility is enforced exclusively through `uv` and a committed `uv.lock`.

## Technical Context

**Language/Version**: Python 3.12+ (uv default; minimum 3.11 if dependency pins require)

**Primary Dependencies**:
- Environment: `uv`, `uv.lock`
- Orchestration: `langchain`, `langgraph`, `langchain-openai` (LM Studio OpenAI-compatible endpoint)
- Local LLM: `qwen/qwen3.6-35b-a3b` via LM Studio (`http://localhost:1234/v1` default)
- Parsing: `docling` (XBRL / `xbrl_conversion` layout configuration)
- Graph: `docling-graph`
- Observability: `mlflow` (LangGraph autolog / tracing integration)
- Judge: `langchain-google-genai` → Gemini 2.5 Pro
- Core typing/IO: `pydantic` v2, `networkx` (graph serialization), `pytest`

**Storage**:
- Raw filings: `data/raw/edgar/{cik}/{accession}/`
- Parsed Docling artifacts: `data/parsed/{graph_id}/`
- Knowledge graphs: `data/graphs/{issuer_id}/{snapshot_id}.graphml` + sidecar `manifest.json`
- MLflow tracking: local `./mlruns/` (dev) or remote tracking URI via env
- Benchmark caches: `data/benchmarks/{dataset}/`

**Testing**: `pytest`, `pytest-asyncio` (if async graph nodes), contract tests per layer boundary under `tests/contract/`

**Target Platform**: Developer workstation (macOS/Linux) with LM Studio for inference; CI runs parsing/graph/eval unit tests without LM Studio (mocked LLM fixtures)

**Project Type**: Multi-package Python monorepo (layer-separated `src/` tree)

**Performance Goals**:
- Ingest + graph build: &lt; 5 min per 10-K on M-series Mac (baseline target)
- Single query macro→meso→micro: &lt; 120 s p95 with local Qwen 35B (quality-first; optimize later)
- Benchmark pilot (100 items/dataset): overnight batch acceptable for v1

**Constraints**:
- Constitution: no flat-string filing index; fail-closed on missing evidence; evaluation layer MUST NOT import retrieval internals beyond contracts
- All installs via `uv sync --locked` only
- Judge model MUST NOT be used for retrieval routing (Gemini evaluation-only)

**Scale/Scope**:
- v1: 10-K/10-Q, English, single-issuer dev corpus + three benchmark pilot subsets
- Modular dataset registry for add/remove without retrieval code changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Docling XBRL pipeline + chunk hashes; synthesis node cites only `EvidenceChunk` IDs; `InsufficientEvidence` terminal state |
| **II. Structural Semantics Preservation** | PASS | Docling `xbrl_conversion` config; docling-graph hierarchical nodes; no vector-only flat index in v1 |
| **III. Traceability** | PASS | MLflow LangGraph autolog; `TrajectoryRecord` contract; mandatory fields per node transition |
| **IV. Separation of Concerns** | PASS | `parsing/`, `graph/`, `retrieval/` (+ `orchestration/`), `evaluation/`; contracts-only cross-layer imports |
| **V. Code Health & Environment Stability** | PASS | Pydantic v2 schemas; `uv.lock`; layer contract tests in CI |
| **VI. Rigorous Agent Evaluation** | PASS | Registry pattern for FinDER/FinAgentBench/FinanceBench; Gemini judge; MRR/MAP/nDCG + trajectory fidelity |

**Post-design re-check**: `data-model.md` and `contracts/` align with four layers; LangGraph lives under `retrieval/orchestration/` only; evaluation imports `contracts` + MLflow client, not LangGraph modules.

## Project Structure

### Documentation (this feature)

```text
specs/001-sec-disclosure-rag/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md              # Phase 2 — /speckit-tasks (not yet created)
```

### Source Code (repository root)

```text
pyproject.toml              # uv project root
uv.lock
.env.example                # LM_STUDIO_BASE_URL, GOOGLE_API_KEY, MLFLOW_TRACKING_URI

src/
├── parsing/
│   ├── edgar_fetch.py      # SEC download helpers
│   ├── docling_pipeline.py # XBRL-aware Docling conversion
│   └── validators.py       # Fail-closed parse QA gates
├── graph/
│   ├── builder.py          # docling-graph → internal GraphDocument
│   ├── store.py            # GraphML + manifest persistence
│   └── query_api.py        # Read-only graph navigation for retrieval
├── retrieval/
│   ├── orchestration/
│   │   ├── state.py        # LangGraph AgentState (typed)
│   │   ├── graph.py        # StateGraph: macro → meso → micro → synthesize
│   │   ├── nodes/
│   │   │   ├── macro_router.py
│   │   │   ├── meso_router.py
│   │   │   └── micro_extractor.py
│   │   └── llm.py          # ChatOpenAI → LM Studio / Qwen
│   ├── synthesis.py        # Grounded answer assembly
│   └── service.py            # Public QueryService façade
├── tracing/
│   └── mlflow_langgraph.py # MLflow setup + LangGraph callback hooks
└── evaluation/
    ├── registry.py         # Dataset/benchmark plugin registry
    ├── runner.py           # Batch benchmark executor
    ├── datasets/
    │   ├── finder.py
    │   ├── finagentbench.py
    │   └── financebench.py
    ├── judges/
    │   └── gemini_panel.py # Gemini 2.5 Pro rubrics
    └── metrics/
        ├── ranking.py      # MRR, MAP, nDCG
        └── trajectory.py   # Trajectory fidelity aggregation

configs/
├── docling_xbrl.yaml       # xbrl_conversion layout options
├── lm_studio.yaml
├── mlflow.yaml
└── judges/
    └── gemini_2_5_pro.yaml

tests/
├── contract/
├── integration/
└── unit/

data/                       # gitignored runtime data
graphs/
mlruns/
```

**Structure Decision**: Single Python monorepo with constitution-aligned layer packages. `tracing/` is a shared utility imported by `retrieval/` only (not a fifth production layer). LangGraph orchestration is nested under `retrieval/orchestration/` per constitution.

## Pipeline Roadmap

### Segment 0: Reproducible Workspace Initialization

| Step | Action |
|------|--------|
| S0.1 | `uv init` at repo root; set `requires-python >= 3.12` |
| S0.2 | Add dependencies with pinned ranges; `uv lock`; commit `uv.lock` |
| S0.3 | `uv sync --locked` in CI and documented dev bootstrap |
| S0.4 | `.env.example` for LM Studio, Google API key, MLflow URI |
| S0.5 | `pytest` + `ruff` + `mypy` (strict on `src/` contracts) in `pyproject.toml` |

**Deliverable**: Empty layer packages importable; CI green on lint-only.

### Segment 1: Ingestion & Graph Building

| Step | Action |
|------|--------|
| S1.1 | Implement EDGAR fetch → `data/raw/` |
| S1.2 | Configure Docling with `xbrl_conversion` paradigm (`configs/docling_xbrl.yaml`) |
| S1.3 | Emit `ParsedDocument` Pydantic objects (sections, tables, footnotes) |
| S1.4 | Run docling-graph builder → `GraphDocument` with `DocumentNode`, `SectionNode`, `ChunkNode` |
| S1.5 | Persist GraphML + `manifest.json` (node counts, parser version, content hashes) |
| S1.6 | Validation gates: structural completeness, numeric spot-check hooks |

**Deliverable**: CLI `uv run ingest --cik …` produces queryable graph snapshot.

### Segment 2: Agentic Retrieval (LangGraph)

| Step | Action |
|------|--------|
| S2.1 | Define `AgentState` (query, macro_plan, filing_set, section_candidates, evidence_chunks, answer, status) |
| S2.2 | `macro_router` node: LangChain + Qwen → temporal scope + filing IDs |
| S2.3 | `meso_router` node: graph `query_api` + Qwen → ranked section paths |
| S2.4 | `micro_extractor` node: chunk/cell selection + Qwen |
| S2.5 | `synthesize` node: grounded answer or `InsufficientEvidence` |
| S2.6 | Compile `StateGraph`; expose `QueryService.answer(query, graph_snapshot_id)` |

**Deliverable**: Programmatic Q&A with citations over one issuer corpus.

### Segment 3: Tracing (MLflow + LangGraph)

| Step | Action |
|------|--------|
| S3.1 | Enable `mlflow.langchain.autolog()` / LangGraph tracing per MLflow 2.x docs |
| S3.2 | Wrap graph invocation: `mlflow.start_run`; log params (model id, graph snapshot) |
| S3.3 | Emit `TrajectoryRecord` artifact JSON per query (constitution fields) |
| S3.4 | Log per-node latency, token usage (from LM Studio callbacks), intermediate state snapshots (redacted if oversized) |

**Deliverable**: Every `QueryService` call traceable by `run_id` in MLflow UI.

### Segment 4: Evaluation Runner

| Step | Action |
|------|--------|
| S4.1 | Dataset registry + adapters (FinDER, FinAgentBench, FinanceBench) |
| S4.2 | `EvaluationRunner`: invoke `QueryService` per item; collect answers + `run_id` |
| S4.3 | Gemini 2.5 Pro judge via `langchain-google-genai` with rubrics (value alignment, claim presence, trajectory fidelity) |
| S4.4 | Metrics: MRR/MAP/nDCG from relevance judgments; stratified reports (qualitative vs quantitative ops: +/-/*//, compositional chains) |
| S4.5 | HTML/JSON report artifact logged to MLflow parent benchmark run |

**Deliverable**: `uv run benchmark --suite pilot` produces reproducible report.

## Complexity Tracking

> No constitution violations requiring justification. Empty by design.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
