# Dataset Generation CLI Contract (011)

**Command group**: `agent-query benchmark-dataset` (Typer sub-app)

## Subcommands

### `generate`

Run full pipeline to **draft** (no registry publish).

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v1.yaml \
  --run-id 20260520-a1b2 \
  [--resume] \
  [--mock-judge]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--config` | yes | GenerationConfig YAML path |
| `--run-id` | yes | Draft directory name under `drafts/` |
| `--resume` | no | Continue from checkpoint in draft dir |
| `--mock-judge` | no | Deterministic stub items (CI only) |

**Exit codes**: `0` draft complete; `2` budget exceeded; `3` validation pass rate below threshold.

**Outputs** (under `data/benchmarks/custom-judge/drafts/{run_id}/`):
- `sampling_manifest.json`
- `corpus/` (materialized)
- `items/candidates.jsonl`
- `items/dev.jsonl` (accepted only)
- `generation_report.json`
- `manifest.json` (`status: draft`)

### `publish`

Promote draft to semver version and register dataset.

```bash
uv run agent-query benchmark-dataset publish \
  --draft-run-id 20260520-a1b2 \
  --version 1.0.0 \
  [--registry]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--draft-run-id` | yes | Source draft |
| `--version` | yes | Semver target directory `v1.0.0` |
| `--registry` | no | Register `custom-judge` in default registry (default true) |

**Preconditions**: `generation_report.pass_rate` ≥ config threshold; `accepted_count` ≥ 200 (v1).

**Outputs**: `data/benchmarks/custom-judge/v1.0.0/` with `status: published`.

### `reproduce`

Rebuild item manifest hash from pinned config + bundle (no EDGAR, no judge).

```bash
uv run agent-query benchmark-dataset reproduce \
  --version 1.0.0 \
  [--verify-lfs]
```

**Exit code**: `0` if recomputed `items_hash` matches manifest; `1` on mismatch.

### `extend`

Create new draft from parent published version + delta config.

```bash
uv run agent-query benchmark-dataset extend \
  --parent-version 1.0.0 \
  --config configs/benchmarks/custom_judge_v1_extend.yaml \
  --run-id 20260521-c3d4
```

**Outputs**: New draft with `parent_version` in manifest; parent directory unchanged.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Gemini generation (unless `--mock-judge`) |
| `USE_MOCK_JUDGE` | CI stub |
| `OFFLINE_BENCHMARK=1` | Block EDGAR during eval/reproduce verify |
| `SEC_EDGAR_USER_AGENT` | Required for `generate` materialize phase only |

## Logging

Structured stderr progress: phase (`sample`, `materialize`, `generate`, `validate`, `bundle`), issuer, budget counters.
