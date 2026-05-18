# Agentic GraphRAG Finance

Multi-stage agentic reasoning over structured SEC disclosures (10-K / 10-Q): live XBRL ingestion, Docling parsing, knowledge-graph navigation, LangGraph orchestration, MLflow trajectories, and modular financial benchmarks.

## Features

| Capability | Branch / entrypoint | Description |
|------------|---------------------|-------------|
| **Core GraphRAG** | `001-sec-disclosure-rag` | Parse filings → build graph → macro/meso/micro retrieval → benchmarks |
| **Live ingestion + CLI** | `002-live-disclosure-cli` | sec-api XBRL fetch/cache + unified `agent-query` CLI |

## Architecture

```text
ingestion/ (sec-api, optional)  →  parsing/ (Docling XBRL)  →  graph/ (docling-graph)
                                        ↓
                         retrieval/orchestration/ (LangGraph: macro → meso → micro → synthesize)
                                        ↓
                              tracing/ (MLflow)     evaluation/ (benchmarks + Gemini judge)
```

Layer boundaries are enforced by contract tests (ingestion does not import graph/retrieval/evaluation; CLI uses `QueryService` only).

**Stack**: [uv](https://docs.astral.sh/uv/), Docling, docling-graph, LangGraph, Qwen via [LM Studio](https://lmstudio.ai/), [sec-api](https://sec-api.io/), MLflow, Google Gemini (judge).

Governed by [.specify/memory/constitution.md](.specify/memory/constitution.md).

## Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- **LM Studio** (or compatible OpenAI API) with Qwen for live `ask` / `sec-query`
- **SEC_API_KEY** from [sec-api.io](https://sec-api.io) for live XBRL fetch (`test-mock` for CI/local mocks)
- **GOOGLE_API_KEY** for benchmark judging (optional with `USE_MOCK_JUDGE=1`)

## Setup

```bash
uv sync --locked
cp .env.example .env
# Edit .env: SEC_API_KEY, LM_STUDIO_*, GOOGLE_API_KEY, MLFLOW_TRACKING_URI=./mlruns
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `uv run agent-query ask` | Live fetch → parse → graph → agentic Q&A (002) |
| `uv run agent-query test` | Structural smoke test (fetch + parse + graph thresholds) |
| `uv run sec-ingest` | Ingest local HTML/PDF into `data/parsed/` |
| `uv run sec-graph-build` | Build graph from parsed JSON (`--issuer` or `--ticker`) |
| `uv run sec-query` | Query existing graph snapshot |
| `uv run sec-benchmark` | Run FinDER / FinAgentBench / FinanceBench pilot |

### `agent-query` (live pipeline)

```bash
# Mock SEC + mock LLM (no external services)
USE_MOCK_LLM=1 SEC_API_KEY=test-mock uv run agent-query ask \
  --ticker AAPL --query "What are total assets?"

# Structural test (no LLM)
SEC_API_KEY=test-mock uv run agent-query test --ticker AAPL --form 10-K

# Live (requires SEC_API_KEY + LM Studio)
uv run agent-query ask --ticker AAPL --query "Summarize revenue drivers." --json
uv run agent-query test --ticker AAPL --check-registry
```

Flags: `--ticker`, `--cik`, `--accession`, `--form` (10-K / 10-Q), `--force-refresh`, `--json`.

### Core pipeline (offline / fixtures)

```bash
uv run sec-ingest --cik 0000320193 \
  --input tests/fixtures/sample_10k.html --skip-docling
uv run sec-graph-build --issuer 0000320193

USE_MOCK_LLM=1 uv run sec-query \
  --snapshot-id <snapshot_id> --issuer-id 0000320193 \
  --question "What are total assets in 2024?"

USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 uv run sec-benchmark \
  --snapshot-id <snapshot_id> --issuer-id 0000320193 --max-items 1
```

### MLflow UI

```bash
uv run mlflow ui --backend-store-uri ./mlruns
```

## Data layout

| Path | Contents |
|------|----------|
| `data/raw/sec_downloads/{ticker}/{accession}/` | Live XBRL packages + `manifest.json` |
| `data/cache/sec-api/` | Ticker→CIK map cache |
| `data/raw/edgar/` | EDGAR downloads (legacy ingest) |
| `data/parsed/` | `ParsedDocument` JSON |
| `data/graphs/` | GraphML + manifests |
| `data/benchmarks/` | Benchmark JSONL |
| `mlruns/` | MLflow runs (gitignored) |

## Testing

CI runs unit, contract, and integration tests with mocks (`SEC_API_KEY=test-mock`, `USE_MOCK_LLM=1`, `USE_MOCK_JUDGE=1`).

```bash
# Lint
uv run ruff check src tests

# Unit + contract (fast)
SEC_API_KEY=test-mock USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 \
  uv run pytest tests/unit tests/contract -q

# Integration (includes agent-query end-to-end mocks)
SEC_API_KEY=test-mock USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 \
  uv run pytest tests/integration -q

# Full suite
SEC_API_KEY=test-mock USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 \
  uv run pytest -q

# Targeted (ingestion + CLI)
SEC_API_KEY=test-mock uv run pytest \
  tests/unit/test_sec_client.py \
  tests/unit/test_xbrl_downloader.py \
  tests/integration/test_agent_query_ask.py \
  tests/integration/test_cache_roundtrip.py -q
```

## Specifications

- [001 SEC disclosure GraphRAG](specs/001-sec-disclosure-rag/plan.md) — core pipeline and benchmarks
- [002 Live disclosure CLI](specs/002-live-disclosure-cli/quickstart.md) — sec-api ingestion and `agent-query`

## Development branches

- `001-sec-disclosure-rag` — core GraphRAG implementation
- `002-live-disclosure-cli` — live ingestion + `agent-query` (builds on 001)
