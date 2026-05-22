# Quickstart: HTML Narrative Supplement (005)

**Branch**: `005-html-narrative-supplement` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- [004 quickstart](../004-docling-graph-materialization/quickstart.md): working `materialize` + `ask` on AAPL
- `uv sync --locked`
- `SEC_EDGAR_USER_AGENT` set (live ingest)
- LM Studio / local LLM for intent router (or `USE_MOCK_LLM=1` to exercise keyword fallback)

## 1. Materialize with HTML narrative (default)

```bash
uv run agent-query materialize --ticker AAPL --force-refresh
```

Verify per accession:

```bash
# Merged parse includes HTML sections
jq '[.sections[] | select(.source_type=="HTML") | .title] | length' \
  data/parsed/AAPL/0000320193-24-000123.json

# Manifest records HTML status
jq '.html_narrative_status' \
  data/raw/sec_downloads/AAPL/0000320193-24-000123/manifest.json
```

## 2. XBRL-only materialize (opt-out)

```bash
uv run agent-query materialize --ticker AAPL --skip-html-narrative
```

Expect `html_narrative_status: skipped` on manifest; parse file has only XBRL-tagged sections.

## 3. Qualitative ask (HTML citation expected)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --query "What are the principal risk factors described in the latest 10-K?"
```

Check JSON output: at least one citation with `"source_type": "HTML"` when narrative indexed.

## 4. Numeric ask (XBRL-primary)

```bash
uv run agent-query ask \
  --ticker AAPL \
  --anchor prior-quarter \
  --query "What was total net sales in the prior quarter?"
```

Citations should be predominantly `XBRL`; trajectory `query_intent` should be `numeric`.

## 5. Router observability (FR-013–016)

After ask, inspect MLflow (or sqlite tracking DB):

```bash
# Params logged on run
uv run python -c "
import mlflow
from tracing.mlflow_langgraph import setup_mlflow
setup_mlflow()
# Use last run id from UI or API
"

# Artifacts: intent_router.json + trajectory.json
```

Required fields in `intent_router.json`:

- `query_intent`, `intent_source`, `source_bias_applied`
- `router_fallback_reason` when `intent_source` is `keyword_fallback`

## 6. Force keyword fallback (dev)

```bash
USE_MOCK_LLM=1 uv run agent-query ask \
  --ticker AAPL \
  --query "Describe management's discussion of liquidity and capital resources."
```

Trajectory MUST show `intent_source=keyword_fallback` and non-empty `router_fallback_reason`.

## 7. Contract tests

```bash
uv run pytest tests/unit/test_intent_router.py tests/unit/test_intent_router_trace.py -q
USE_FIXTURE_INGESTION=1 uv run pytest tests/integration/test_ask_html_citation.py -q
```

## Troubleshooting

| Symptom | Action |
|---------|--------|
| No HTML sections in parse | Check inline HTML in cache; try fallback `.htm`; see `html_narrative_status=failed` |
| Qualitative ask, only XBRL citations | Confirm HTML nodes in graph (`properties.source_type`); check `query_intent` in trajectory |
| Missing router fields in trajectory | Ensure `intent_router` node runs before `micro_extractor`; upgrade breaks SC-006 |
| `intent_source=llm` but mock mode | Bug: must be `keyword_fallback` per FR-014 |
