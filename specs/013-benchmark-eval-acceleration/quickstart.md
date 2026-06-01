# Quickstart: Benchmark Evaluation Acceleration (013)

**Feature**: 013-benchmark-eval-acceleration | **Date**: 2026-06-01

**Prerequisites**: Feature 012 merged; `releases/paper-v1.0/manifest.yaml`; custom-judge v1.0.0 LFS corpus; `GOOGLE_API_KEY`; LM Studio for graph variants.

## Recommended: defer judge + resume (faster generation)

```bash
export OFFLINE_BENCHMARK=1
export REPRO_DEFER_JUDGE=1
export USE_MOCK_JUDGE=0
export USE_MOCK_LLM=0

uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --defer-judge \
  --resume
```

**What happens**:

1. Verify corpus + relevance gate (012)
2. For each variant: run agents on items **without** Gemini per item
3. After each variant: `judge-batch` scores pending items (default concurrency 2)
4. Export tables when all judges complete

Interrupt anytime (Ctrl+C); re-run the **same command** to resume items/variants.

## Judge batch only (generation already done)

```bash
export OFFLINE_BENCHMARK=1

uv run agent-query repro judge-batch \
  --output reports/repro-paper-v1.0 \
  --concurrency 2
```

Or:

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --judge-only
```

## Export tables without re-running agents

```bash
uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0
```

Use `--allow-pending-export` only for partial reports (audit table lists pending items).

## Fresh start (no resume)

```bash
rm -rf reports/repro-paper-v1.0   # or use a new --output path

uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0-fresh \
  --no-resume \
  --defer-judge
```

## Reset a single variant

```bash
rm -rf reports/repro-paper-v1.0/graph-full
# Edit repro_run.json to remove graph-full from completed_variants, or use --no-resume on full output dir
```

## Smoke test (CI / local)

```bash
export OFFLINE_BENCHMARK=1 USE_MOCK_JUDGE=1 USE_MOCK_LLM=1 REPRO_DEFER_JUDGE=1

uv run agent-query repro run-all \
  --manifest releases/paper-smoke/manifest.yaml \
  --output reports/repro-smoke-defer \
  --max-items 5 \
  --defer-judge
```

**SC-001 release validation** (20 items, slower — run before paper repro):

```bash
uv run pytest -m slow tests/integration/test_repro_defer_judge_smoke.py -q
```

**SC-002 judge-batch restart** (integration):

```bash
uv run pytest tests/integration/test_repro_judge_batch_restart.py -q
```

## Verify progress

```bash
jq 'length' reports/repro-paper-v1.0/graph-full/results.json
jq '[.[] | select(.judge_status=="pending")] | length' reports/repro-paper-v1.0/graph-full/results.json
cat reports/repro-paper-v1.0/repro_run.json
```

## Environment reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `REPRO_DEFER_JUDGE` | `0` | Defer judging (or use `--defer-judge`) |
| `REPRO_JUDGE_CONCURRENCY` | `2` | Parallel Gemini judge calls |
| `REPRO_JUDGE_AFTER` | `each_variant` | `each_variant` or `all_variants` |

Full recovery playbook: [docs/research-reproduction.md](../../docs/research-reproduction.md) (updated in implementation).
