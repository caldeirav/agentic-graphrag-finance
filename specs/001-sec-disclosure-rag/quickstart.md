# Quickstart: Agentic SEC Disclosure RAG

**Branch**: `001-sec-disclosure-rag` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- [LM Studio](https://lmstudio.ai/) running with `qwen/qwen3.6-35b-a3b` loaded (OpenAI-compatible server on port 1234)
- Google API key for Gemini judge (evaluation only)
- SEC EDGAR network access

## Segment 0: Workspace

```bash
cd /path/to/agentic-graphrag-finance
uv init                    # skip if pyproject.toml exists
uv add langchain langgraph langchain-openai langchain-google-genai \
       docling docling-graph mlflow pydantic networkx pytest ruff mypy
uv lock
uv sync --locked
cp .env.example .env       # fill keys below
```

`.env` variables:

```bash
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3.6-35b-a3b
GOOGLE_API_KEY=your_gemini_key
MLFLOW_TRACKING_URI=./mlruns
```

Verify LM Studio:

```bash
curl -s "$LM_STUDIO_BASE_URL/models" | head
```

## Segment 1: Ingest & build graph

```bash
# Example: ingest Apple FY24 10-K (replace with target CIK/accession)
uv run python -m parsing.cli ingest \
  --cik 0000320193 \
  --forms 10-K,10-Q \
  --limit 2 \
  --out data/raw/

uv run python -m graph.cli build \
  --issuer 0000320193 \
  --parsed-dir data/parsed/ \
  --out data/graphs/
```

Inspect output:

```bash
ls data/graphs/0000320193/
# expect: <snapshot_id>.graphml  manifest.json
```

## Segment 2–3: Query with tracing

```bash
uv run python -m retrieval.cli query \
  --snapshot-id <snapshot_id> \
  --question "How did total current assets change year over year in the latest 10-K?"
```

Open MLflow UI:

```bash
uv run mlflow ui --backend-store-uri ./mlruns
```

Confirm run contains LangGraph spans and `trajectory.json` artifact.

## Segment 4: Benchmark pilot

Download benchmark assets per dataset README into `data/benchmarks/{finder,finagentbench,financebench}/`.

```bash
uv run python -m evaluation.cli benchmark \
  --suite pilot \
  --snapshot-id <snapshot_id> \
  --datasets finder,finagentbench,financebench \
  --max-items 100
```

Reports appear under `./mlruns/` and `reports/benchmark-<timestamp>/`.

## Run tests

```bash
uv run pytest tests/contract -q
uv run pytest tests/unit -q
# integration tests require LM Studio or USE_MOCK_LLM=1
USE_MOCK_LLM=1 uv run pytest tests/integration -q
```

## Pipeline segment map

| Segment | Module path | CLI (planned) |
|---------|-------------|---------------|
| 0 | `pyproject.toml`, `uv.lock` | `uv sync --locked` |
| 1 | `src/parsing/`, `src/graph/` | `parsing.cli ingest`, `graph.cli build` |
| 2 | `src/retrieval/orchestration/` | `retrieval.cli query` |
| 3 | `src/tracing/` | automatic on query |
| 4 | `src/evaluation/` | `evaluation.cli benchmark` |

## Constitution reminders

- Do not use `pip install` — only `uv`
- Gemini is for **evaluation judges only**, not retrieval nodes
- LangGraph code lives under `retrieval/orchestration/`, not a top-level `agent/` package
