# Quickstart: Ask Console Trajectory Trace (007)

**Branch**: `007-ask-console-trace` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Merged **005** on branch: materialized AAPL corpus, working `ask`
- `uv sync --locked`
- LM Studio for live trace (or `USE_MOCK_LLM=1` for deterministic fallback labels)

## 1. Normal trace (streaming stderr)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors?" \
  --trace normal
```

Expect:

- **stderr**: staged panels (`macro_router` → `intent_router` → `meso_router` → `micro_extractor` → `synthesize`) as each completes
- **stdout**: answer text + status footer (snapshot, MLflow run, citations)

## 2. Quiet mode (baseline-like)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors?" \
  --trace quiet
```

Only minimal footer on stdout; no stage panels on stderr.

## 3. Pipe-safe JSON

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What was revenue in the prior quarter?" \
  --anchor prior-quarter \
  --json --trace quiet 2>/dev/null | jq .status
```

stdout is pure JSON; stderr suppressed.

## 4. Machine-readable trace (JSONL on stderr)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors?" \
  --trace quiet --trace-json \
  2> /tmp/ask-trace.jsonl

wc -l /tmp/ask-trace.jsonl   # expect ≥1 line per completed stage
head -1 /tmp/ask-trace.jsonl | jq .
```

## 5. CI / non-TTY default + env override

```bash
AGENT_QUERY_TRACE=normal uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors?" \
  --trace normal
```

Without TTY, default is `quiet` unless `AGENT_QUERY_TRACE` or `--trace` is set.

## 6. Verbose LLM previews

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors?" \
  --trace verbose
```

Synthesis (and router when LLM runs) show truncated prompt/response bodies per `configs/trace.yaml`.

## 7. Verify registry contract (developers)

```bash
uv run pytest tests/contract/test_ask_trace_registry.py -q
```

Fails if a LangGraph node is added without a registry entry.

## 8. Compare with MLflow

After ask, open MLflow run — `trajectory.json` and `intent_router.json` should align with stderr fields (intent, filings, evidence counts).
