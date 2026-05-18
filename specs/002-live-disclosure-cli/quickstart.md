# Quickstart: Live Disclosure CLI

**Branch**: `002-live-disclosure-cli` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Completed `001-sec-disclosure-rag` workspace (`uv sync --locked`)
- [sec-api.io](https://sec-api.io) API key
- LM Studio with Qwen (for `ask` mode)
- `.env` configured:

```bash
SEC_API_KEY=your_sec_api_key_here
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3.6-35b-a3b
MLFLOW_TRACKING_URI=./mlruns
```

## Phase 0: Install sec-api

```bash
uv add sec-api typer
uv lock
uv sync --locked
```

Verify key loading:

```bash
uv run python -c "from ingestion.settings import require_sec_api_key; require_sec_api_key(); print('ok')"
```

## Phase 1A: Fetch live XBRL (library)

```bash
uv run python -c "
from ingestion import fetch_filing
entry = fetch_filing(ticker='AAPL', form_type='10-K')
print(entry.local_path, entry.parse_ready, entry.cache_hit)
"
```

Artifacts land in `data/raw/sec_downloads/AAPL/<accession>/`.

## Phase 5: Unified CLI

### Live query

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What changed in lease obligations footnotes between the last two quarterly filings?"
```

### Structural test (no LLM)

```bash
uv run agent-query test --ticker AAPL --form 10-K
```

### JSON output for scripting

```bash
uv run agent-query ask --ticker MSFT --query "Total revenue?" --json
```

## MLflow

```bash
uv run mlflow ui --backend-store-uri ./mlruns
```

Look for runs prefixed `agent-query-`.

## CI / mocks

```bash
export SEC_API_KEY=test-mock
export USE_MOCK_LLM=1
uv run pytest tests/ingestion tests/cli -q
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| `SEC_API_KEY not set` | Add to `.env` (never commit) |
| Empty XBRL package | Retry with `--force-refresh`; check accession |
| Slow repeat runs | Second run should hit cache (check `cache_hit` in manifest) |
