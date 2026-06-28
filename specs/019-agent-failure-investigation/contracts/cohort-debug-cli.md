# Contract: Cohort Debug CLI

**Feature**: 019 | **Command**: `repro cohort-debug`

## Usage

```bash
# Default: re-run agent + judge with trace
uv run agent-query repro cohort-debug \
  --cohort data/benchmarks/custom-judge/drafts/quality-v2.0.1/tier1_cohort.json \
  --manifest releases/paper-v1.1/manifest.yaml \
  --output reports/repro-cohort-debug/run-001 \
  [--variant graph-full] \
  [--trace normal] \
  [--trace-json]

# Replay from existing checkpoints (no agent re-exec)
uv run agent-query repro cohort-debug \
  --cohort tier1_cohort.json \
  --manifest releases/paper-v1.1/manifest.yaml \
  --replay-input reports/repro-paper-v1.0 \
  --output reports/repro-cohort-debug/replay-001
```

## Environment

- `USE_MOCK_LLM`, `USE_MOCK_JUDGE`, `USE_FIXTURE_INGESTION`, `OFFLINE_BENCHMARK=1` (same as repro)
- Re-run mode sets `trace_level: normal` on query metadata (overrides runner quiet default for cohort items only)

## Outputs

| Path | Description |
|------|-------------|
| `{output}/graph-full/results.json` | Cohort subset results |
| `{output}/cohort_debug/{item_id}.summary.json` | `CohortDebugSummary` schema |
| `{output}/cohort_debug/trace.jsonl` | Aggregated trace events (optional) |

## Stdout progress line format

One line per completed item:

```text
[item={item_id} variant={variant} synthesis_path={path} citations={n} outcome={score} weakest={criterion}]
```

## Resume

On partial failure, `--resume` skips items with existing `summary.json` unless `--force`.
