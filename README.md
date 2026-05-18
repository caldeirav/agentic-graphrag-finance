# Agentic GraphRAG Finance

Multi-stage agentic reasoning over structured SEC disclosures (10-K / 10-Q) with knowledge-graph navigation, MLflow trajectories, and modular financial benchmarks.

## Architecture

```text
parsing/  →  graph/  →  retrieval/orchestration/  →  (offline) evaluation/
              ↑              LangGraph macro/meso/micro + Qwen (LM Studio)
         Docling XBRL                    MLflow traces
```

See [specs/001-sec-disclosure-rag/plan.md](specs/001-sec-disclosure-rag/plan.md) and [quickstart.md](specs/001-sec-disclosure-rag/quickstart.md).

## Quick start

```bash
uv sync --locked
cp .env.example .env

# Ingest + build graph (local HTML or EDGAR)
uv run python -m parsing.cli --cik 0000320193 --input tests/fixtures/sample_10k.html --skip-docling
uv run python -m graph.cli --issuer 0000320193

# Query (USE_MOCK_LLM=1 for CI / no LM Studio)
USE_MOCK_LLM=1 uv run python -m retrieval.cli \
  --snapshot-id <snapshot_id> --issuer-id 0000320193 \
  --question "What are total assets in 2024?"

# Benchmark pilot
USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 uv run python -m evaluation.cli \
  --snapshot-id <snapshot_id> --issuer-id 0000320193 --max-items 1
```

## Data directories

- `data/raw/edgar/` — downloaded filings
- `data/parsed/` — `ParsedDocument` JSON
- `data/graphs/` — GraphML + manifests
- `data/benchmarks/` — FinDER, FinAgentBench, FinanceBench JSONL

## Development

```bash
uv run pytest tests/unit tests/contract -q
USE_MOCK_LLM=1 uv run pytest tests/integration -q
```

Governed by [.specify/memory/constitution.md](.specify/memory/constitution.md) (uv-only, layer separation, MLflow traceability).
