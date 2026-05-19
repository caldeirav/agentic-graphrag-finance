# Graph-Grounded Agentic Retrieval over XBRL Financial Disclosures

An **Agentic GraphRAG** system for answering natural-language questions over SEC regulatory filings (10-K, 10-Q). It ingests real **XBRL** packages from EDGAR, builds **hierarchical knowledge graphs** with [Docling](https://github.com/docling-project/docling) and [docling-graph](https://github.com/docling-project/docling-graph), and runs a **multi-stage LangGraph agent** that reasons over document scope, graph structure, and granular evidence before synthesizing a grounded answer.

This repository implements the research direction described in *Graph-Grounded Agentic Retrieval: Enhancing Multi-Stage Reasoning over XBRL Financial Disclosures* — transforming dense, structured financial disclosures into navigable graphs and measuring agent decision paths with MLflow trajectories and modular benchmarks.

---

## What it does

| Stage | What happens |
|-------|----------------|
| **Ingest** | Resolve ticker/CIK/accession via SEC EDGAR; download full XBRL instance + taxonomy linkbases (no third-party filing APIs). |
| **Parse** | Mandatory [Docling XBRL conversion](https://docling-project.github.io/docling/examples/xbrl_conversion/) (`InputFormat.XML_XBRL`) — sections, tables, and consolidated numeric facts. No HTML fallback. |
| **Graph** | Map `ParsedDocument` → `GraphSnapshot`: documents → sections → chunks; XBRL facts indexed as first-class paragraph chunks with human-readable excerpts. |
| **Retrieve** | LangGraph agent: **macro** (temporal intent) → **meso** (section routing) → **micro** (chunk/XBRL extraction) → **synthesize** (LLM-grounded answer + citations). |
| **Observe** | MLflow runs, LangGraph trajectories, and optional Gemini judge for benchmark suites. |

The primary entry point is a single command that runs the full pipeline:

```bash
uv run agent-query ask --ticker AAPL --query "What was net sales?"
```

---

## Architecture

```mermaid
flowchart TB
    subgraph ingest ["Ingestion (src/ingestion/)"]
        EDGAR["SEC EDGAR<br/>ticker · CIK · accession"]
        XBRL["XBRL package<br/>instance + linkbases"]
        EDGAR --> XBRL
    end

    subgraph parse ["Parsing (src/parsing/)"]
        Docling["Docling XML_XBRL<br/>+ xbrl_facts"]
        XBRL --> Docling
    end

    subgraph graph ["Graph (src/graph/)"]
        Snap["GraphSnapshot<br/>GraphML + manifest"]
        Docling --> Snap
    end

    subgraph agent ["Agent (src/retrieval/orchestration/)"]
        M["macro_router<br/>filing · temporal scope"]
        Me["meso_router<br/>section candidates"]
        Mi["micro_extractor<br/>chunks · XBRL facts"]
        S["synthesize<br/>grounded answer"]
        M --> Me --> Mi --> S
    end

    Snap --> M
    S --> Out["Answer + citations<br/>MLflow trajectory"]

    subgraph eval ["Evaluation (src/evaluation/)"]
        Bench["FinDER · FinAgentBench<br/>FinanceBench"]
    end

    Snap -.-> Bench
```

**Layer boundaries** (enforced by contract tests): ingestion does not import graph/retrieval; the CLI talks to retrieval only through `QueryService`.

### Multi-stage agent

The agent is a compiled **LangGraph** `StateGraph` with four nodes:

```mermaid
stateDiagram-v2
    [*] --> macro_router
    macro_router --> meso_router: MacroPlan · filing set
    meso_router --> micro_extractor: Section candidates (scored)
    micro_extractor --> synthesize: Evidence chunks (top-K)
    synthesize --> [*]: AnswerPackage · status
```

| Node | Role | Implementation notes |
|------|------|----------------------|
| **macro_router** | Intent and temporal framing | LLM selects comparison mode (YoY / QoQ / sequential) and filing context; falls back safely when the model returns null or invalid modes. |
| **meso_router** | Structural navigation | Ranks graph **sections** by query overlap; boosts MD&A, revenue-related labels, and the **XBRL Financial Facts** section for numeric questions. |
| **micro_extractor** | Granular evidence | Pulls table rows, paragraphs, and XBRL fact chunks; relevance scoring with extra weight for XBRL concepts matching the query (e.g. revenue, assets). |
| **synthesize** | Grounded generation | LLM answer constrained to retrieved evidence; returns `INSUFFICIENT_EVIDENCE` when the corpus lacks support. |

### Technical stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.12+, [uv](https://docs.astral.sh/uv/) |
| Filings | SEC EDGAR (`SEC_EDGAR_USER_AGENT`, rate-limited) |
| Parsing | Docling `docling[xbrl]>=2.94.0` (Arelle-backed) |
| Graph | NetworkX / GraphML, docling-graph mapper |
| Orchestration | LangGraph, LangChain OpenAI-compatible client |
| LLM (local) | [LM Studio](https://lmstudio.ai/) — default Qwen via OpenAI API |
| Judge (benchmarks) | Google Gemini |
| Observability | MLflow (SQLite backend recommended) |

Governed by [.specify/memory/constitution.md](.specify/memory/constitution.md). Deeper design notes: [research-xbrl-retrieval.md](specs/002-live-disclosure-cli/research-xbrl-retrieval.md).

---

## Prerequisites

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/)
- **LM Studio** (or any OpenAI-compatible server) with a chat model loaded and the local server enabled — required for live `ask` when `USE_MOCK_LLM=0`
- **`SEC_EDGAR_USER_AGENT`** — your name and email per [SEC fair access](https://www.sec.gov/os/webmaster-faq#code-support)
- **`GOOGLE_API_KEY`** — for benchmark judging (`USE_MOCK_JUDGE=1` skips this in CI)

---

## Setup

```bash
git clone <repo-url> && cd agentic-graphrag-finance
uv sync --locked
cp .env.example .env
```

Edit `.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SEC_EDGAR_USER_AGENT` | Yes (live ingest) | `Your Name you@example.com` for EDGAR |
| `LM_STUDIO_BASE_URL` | Yes (live ask) | Default `http://localhost:1234/v1` |
| `LM_STUDIO_MODEL` | Yes (live ask) | Model id exposed by LM Studio |
| `MLFLOW_TRACKING_URI` | Recommended | `sqlite:///mlflow.db` (project default) |
| `GOOGLE_API_KEY` | Benchmarks | Gemini judge |
| `USE_MOCK_LLM` | Optional | `1` = template answers, no LM Studio |
| `USE_MOCK_JUDGE` | Optional | `1` = skip Gemini in benchmarks |
| `USE_FIXTURE_INGESTION` | Optional | `1` = bundled XBRL under `tests/fixtures/` |

> **Note:** If your shell exports `MLFLOW_TRACKING_URI=./mlruns`, the app maps that to SQLite from `configs/mlflow.yaml`. Prefer `sqlite:///mlflow.db` in `.env`. Do not use bash placeholders like `${VAR:-default}` in config files.

Start LM Studio, load your model, and enable the local server before running live queries.

---

## CLI usage

### `agent-query` — unified live pipeline

| Command | Description |
|---------|-------------|
| `ask` | Fetch → parse → build graph → run agent → print answer |
| `test` | Structural smoke test (fetch, parse, graph node counts; no LLM) |
| `mlflow-clean` | Reset SQLite tracking DB and remove legacy `mlruns/` dirs |

#### Ask

```bash
# Live: EDGAR + Docling + LM Studio
uv run agent-query ask \
  --ticker AAPL \
  --query "What was net sales?"

# Machine-readable output
uv run agent-query ask --ticker AAPL --query "Summarize revenue drivers." --json

# Re-download and rebuild graph after parser/graph changes
uv run agent-query ask --ticker AAPL --query "..." --force-refresh
```

**Identifiers** (provide at least one):

| Flag | Description |
|------|-------------|
| `--ticker` / `-t` | Resolve CIK and latest filing for form type |
| `--cik` | Direct CIK (validated against ticker if both given) |
| `--accession` / `-a` | Specific filing accession number |
| `--form` / `-f` | `10-K` (default) or `10-Q` |
| `--force-refresh` | Bypass cached XBRL under `data/raw/` |
| `--json` | Emit full `CLIAskResult` JSON |

**Example output:**

```text
Apple reported net sales of $307.0 billion for the fiscal year ended September 28, 2025 ...

Status: SUCCESS
Snapshot: fc95ac52-6828-4b88-8992-d14f4722a691
MLflow run: 2de3797c2bed48dfb306f2899f51b931
Citations: 3
Timings (ms): fetch=1200, parse=8500, graph=12, query=3400
```

#### Test (offline / CI)

```bash
USE_FIXTURE_INGESTION=1 uv run agent-query test --ticker AAPL --form 10-K
USE_FIXTURE_INGESTION=1 uv run agent-query test --ticker AAPL --check-registry --json
```

#### MLflow cleanup

```bash
uv run agent-query mlflow-clean
```

### Staged pipeline — research and debugging

Use these when you want to inspect intermediate artifacts without re-running the agent:

```bash
# 1. Ingest + parse → data/parsed/
USE_FIXTURE_INGESTION=1 uv run sec-ingest --ticker AAPL --form 10-K

# 2. Build graph → data/graphs/{issuer}/
uv run sec-graph-build --ticker AAPL

# 3. Query existing snapshot
USE_MOCK_LLM=1 uv run sec-query \
  --snapshot-id <uuid> \
  --issuer-id AAPL \
  --question "What are total assets?"

# 4. Benchmark retrieval paths (pilot suite)
USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 uv run sec-benchmark \
  --snapshot-id <uuid> \
  --issuer-id AAPL \
  --max-items 5
```

| Script | Module | Purpose |
|--------|--------|---------|
| `sec-ingest` | `parsing.cli` | Fetch/parse XBRL to `ParsedDocument` JSON |
| `sec-graph-build` | `graph.cli` | Build `GraphSnapshot` from parsed docs |
| `sec-query` | `retrieval.cli` | Run LangGraph agent on a snapshot |
| `sec-benchmark` | `evaluation.cli` | FinDER / FinAgentBench / FinanceBench pilot |

### MLflow UI

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Open the printed URL to inspect runs, tags (`ticker`, `accession`, `cik`), and exported agent trajectories.

---

## Data layout

| Path | Contents |
|------|----------|
| `data/raw/sec_downloads/{ticker}/{accession}/` | EDGAR XBRL package + `manifest.json` |
| `data/cache/edgar/` | Cached `company_tickers.json` |
| `data/parsed/` | `ParsedDocument` JSON per filing |
| `data/graphs/{issuer}/` | `{snapshot_id}.graphml` + `.manifest.json` |
| `data/benchmarks/` | Benchmark JSONL inputs |
| `tests/fixtures/sec_downloads/` | Offline XBRL for CI (`USE_FIXTURE_INGESTION=1`) |
| `mlflow.db` | SQLite tracking store (gitignored) |

---

## Testing

```bash
uv run ruff check src tests

USE_FIXTURE_INGESTION=1 USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 \
  SEC_EDGAR_USER_AGENT="Test test@example.com" \
  uv run pytest -q
```

Contract tests verify import boundaries between layers. Integration tests may require LM Studio or mocks.

---

## Project layout

```text
src/
  ingestion/     EDGAR client, XBRL downloader
  parsing/       Docling XBRL pipeline, fact consolidation
  graph/         Snapshot builder, GraphML store, query API
  retrieval/     LangGraph orchestration, synthesis, QueryService
  evaluation/    Benchmark registry and Gemini judge
  tracing/       MLflow setup, trajectories, cleanup
  cli/           agent-query (ask · test · mlflow-clean)
  models/        Pydantic domain types and enums
  contracts/     Service interfaces
```

---

## Specifications

| Document | Scope |
|----------|-------|
| [001 plan](specs/001-sec-disclosure-rag/plan.md) | Core GraphRAG pipeline and benchmarks |
| [002 quickstart](specs/002-live-disclosure-cli/quickstart.md) | Live EDGAR ingestion and CLI contracts |
| [XBRL research](specs/002-live-disclosure-cli/research-xbrl-retrieval.md) | XBRL-first retrieval design |
