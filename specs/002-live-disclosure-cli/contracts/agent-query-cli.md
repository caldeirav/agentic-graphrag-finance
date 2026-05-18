# agent-query CLI Contract

**Entry**: `uv run agent-query [COMMAND] [OPTIONS]`  
**Implementation**: `src/cli/main.py`

## Commands

### `ask` — Live Query Execution Mode

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "Examine lease obligations footnote changes between Q2 and Q3" \
  [--form 10-K] [--form 10-Q] \
  [--cik 0000320193] \
  [--accession 0000320193-24-000123] \
  [--force-refresh] \
  [--snapshot-id UUID] \
  [--json]
```

**Orchestration** (sequential, fail-fast):
1. Validate `SEC_API_KEY` present
2. `ingestion.fetch_filing(...)`
3. `parsing.parse_sec_download(cache_entry)`
4. `graph.builder.build_snapshot` + `graph.store.save_snapshot`
5. `retrieval.QueryService.answer(QueryRequest)`
6. Print `CLIAskResult` to stdout

**Exit codes**:
- `0` — success or `INSUFFICIENT_EVIDENCE` (valid fail-closed)
- `1` — configuration error (missing key)
- `2` — fetch/validation failure
- `3` — pipeline error

### `test` — Testing / Evaluation Mode

```bash
uv run agent-query test \
  --ticker AAPL \
  [--form 10-K] \
  [--accession ...] \
  [--min-sections 3] \
  [--min-chunk-tables 1]
```

**Behavior**:
- Fetch (or cache hit) → parse → graph build
- Assert structural thresholds (no LLM required)
- Optional: `--check-registry` loads JSON thresholds from spec contracts

**Exit codes**:
- `0` — all assertions passed
- `1` — assertion failure
- `2` — fetch/parse failure

## Environment

| Variable | Required for |
|----------|----------------|
| `SEC_API_KEY` | `ask`, `test` (live fetch) |
| `LM_STUDIO_*` | `ask` only |
| `USE_MOCK_LLM` | Optional CI shortcut for `ask` |

## Output format (human default)

```text
Ticker: AAPL | Filings: 10-Q (2024-Q3), 10-Q (2024-Q2)
Snapshot: <uuid> | MLflow: <run_id>

Answer:
<grounded text>

Citations:
[1] chunk-id: excerpt...
```

JSON mode (`--json`): `CLIAskResult.model_dump_json()`
