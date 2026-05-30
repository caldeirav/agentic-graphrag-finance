# Quickstart: Judge-Generated Custom Evaluation Dataset (012)

**Feature**: 012-judge-eval-dataset | **Date**: 2026-05-20

## Prerequisites

- `uv sync --locked`
- `.env` with `GOOGLE_API_KEY`, `SEC_EDGAR_USER_AGENT`
- Git LFS installed (`git lfs install`)
- Apple/other issuers: network for **generate/materialize only** (not eval)

## 1. Build issuer allowlist (one-time)

```bash
uv run python scripts/build_issuer_allowlist.py \
  --output configs/benchmarks/issuer_allowlist_v1.json
```

Verify hash recorded in upcoming sampling manifest.

## 2. Generate draft dataset

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v1.yaml \
  --run-id pilot-20260520
```

Phases: sample issuers → materialize XBRL/graph per ticker → Gemini item generation → validate → write draft under `data/benchmarks/custom-judge/drafts/pilot-20260520/`.

Review `generation_report.json` — require `pass_rate` ≥ 0.95 and `accepted_count` ≥ 200.

## 3. Publish version

```bash
uv run agent-query benchmark-dataset publish \
  --draft-run-id pilot-20260520 \
  --version 1.0.0
```

Promotes to `data/benchmarks/custom-judge/v1.0.0/` and registers `custom-judge` adapter.

## 4. Pull LFS corpus (third-party reproduction)

```bash
git lfs pull --include="data/benchmarks/custom-judge/v1.0.0/corpus/**"
```

## 5. Verify reproduce hash (offline)

```bash
OFFLINE_BENCHMARK=1 uv run agent-query benchmark-dataset reproduce \
  --version 1.0.0 \
  --verify-lfs
```

Expect exit code `0` and matching `items_hash`.

## 6. Run evaluation smoke (offline, ≥20 items)

```bash
OFFLINE_BENCHMARK=1 USE_MOCK_LLM=1 USE_MOCK_JUDGE=1 \
  uv run agent-query test \
  --datasets custom-judge \
  --snapshot-id "$(jq -r .corpus_bundle.snapshot_id data/benchmarks/custom-judge/v1.0.0/manifest.json)" \
  --max-items 20 \
  --suite dev
```

Or via evaluation runner with bundle graph root override (see plan Phase E).

Confirm MLflow parent run includes `custom_judge_version` and judge pins.

## 7. Extend dataset (optional)

```bash
uv run agent-query benchmark-dataset extend \
  --parent-version 1.0.0 \
  --config configs/benchmarks/custom_judge_v1_extend.yaml \
  --run-id extend-20260521
```

Review draft → publish as `1.1.0`.

## CI / mock path

```bash
USE_MOCK_JUDGE=1 uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_ci.yaml \
  --run-id ci-fixture \
  --mock-judge
```

Uses tiny allowlist + 3 issuers under `tests/fixtures/custom_judge/`.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| LFS objects missing | `git lfs pull` + check `artifact_hashes` in manifest |
| `pass_rate` below threshold | Inspect `generation_report.rejections_by_reason`; tune prompts or retries |
| Section path validation failures | Regenerate after graph index export fix; check `corpus/graph_node_index.json` |
| EDGAR rate limit during generate | Reduce `issuer_sample_count`; re-run with `--resume` |

## Related docs

- [plan.md](./plan.md)
- [data-model.md](./data-model.md)
- [contracts/dataset-generation-cli.md](./contracts/dataset-generation-cli.md)
- Feature 010 judge: [quickstart](../010-mlflow-trajectory-judge-eval/quickstart.md)
