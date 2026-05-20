# Quickstart: Multi-Filing Issuer Corpus (003)

**Branch**: `003-multi-filing-corpus` | **Plan**: [plan.md](./plan.md)

**Prerequisite**: `002-live-disclosure-cli` complete (`uv sync --locked`, `EDGAR_USER_AGENT` in `.env`, LM Studio for `ask`).

## 1. Materialize default issuer corpus

Build latest 10-K + 4 trailing 10-Q into one graph snapshot:

```bash
uv run agent-query materialize --ticker AAPL
```

Expected:
- Cache dirs under `data/raw/sec_downloads/AAPL/{accession}/`
- Parsed docs `data/parsed/AAPL/{accession}.json`
- Graph `data/graphs/AAPL/{snapshot_id}.graphml` + `index.json` updated

## 2. Ask with temporal scope (NL)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "How do supply chain risks in the latest annual report compare to the prior quarter?"
```

Expected terminal sections:
- Grounded answer
- **Snapshot scope** with bound accessions and fiscal period labels
- Stale warning if EDGAR has newer filings than the snapshot

## 3. Ask with explicit fiscal flags

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "Revenue comparison" \
  --compare FY2024-Q3,FY2024-Q2
```

Explicit flags override NL period inference.

## 4. Reuse snapshot (warn if stale)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --snapshot-id <uuid-from-materialize> \
  --query "Summarize latest annual MD&A risks"
```

## 5. Corpus cap validation

Requesting &gt;12 filings without narrowing must error:

```bash
# Example: explicit accession list exceeding cap (when implemented)
uv run agent-query materialize --ticker AAPL --accessions <13+ accessions>
```

## 6. Benchmark binding smoke

```bash
uv run python -m pytest tests/integration/test_corpus_binding.py -q
```

Benchmark cases require `temporal_scope` in registry JSON ([temporal-scope.md](./contracts/temporal-scope.md)).

## 7. Inspect MLflow manifest

```bash
uv run mlflow ui --backend-store-uri ./mlruns
```

Open latest `agent-query` run → artifact `binding_manifest.json`.
