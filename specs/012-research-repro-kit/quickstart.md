# Quickstart: Research Reproduction Kit (012)

**Feature**: 012-research-repro-kit | **Date**: 2026-05-30

## Prerequisites

- Checkout release tag `paper-v1.0` (or feature branch with `releases/paper-v1.0/manifest.yaml`)
- `uv sync --locked --extra reproduction` (installs `sentence-transformers` for flat-chunk)
- Git LFS: `git lfs pull --include="data/benchmarks/custom-judge/v1.0.0/corpus/**"`
- `.env`: `GOOGLE_API_KEY` (live judge), LM Studio or pinned remote LLM per manifest
- Published custom-judge v1.0.0 bundle (≥200 items, feature 011 publish gate)

## 1. Verify frozen corpus (offline)

```bash
export OFFLINE_BENCHMARK=1

uv run agent-query repro verify-corpus \
  --manifest releases/paper-v1.0/manifest.yaml
```

Expect all `corpus_hashes` to match. On mismatch, re-run `git lfs pull` or check bundle path.

## 2. Materialize graph-grounded relevance labels

Skip if published bundle already includes `relevance_labels_hash` with coverage ≥ 90%.

```bash
uv run agent-query repro materialize-relevance \
  --manifest releases/paper-v1.0/manifest.yaml
```

Inspect `relevance_report.json` — require `coverage_rate` ≥ 0.90.

## 3. Full paper reproduction (five variants)

```bash
OFFLINE_BENCHMARK=1 \
USE_MOCK_JUDGE=0 \
USE_MOCK_LLM=0 \
uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0
```

Runs on **full `dev` split**, live agent + judge, variants:
`graph-full`, `flat-chunk`, `ablation-no-macro`, `ablation-no-walker`, `ablation-xbrl-only`.

**Reference bounds** (see `research.md` R9):
- ~8 h wall-clock on 8 vCPU / 32 GB RAM with LFS pre-pulled
- ~2–4 GB LFS download for v1 corpus

## 4. Verify tables against release checksums

```bash
uv run agent-query repro verify-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0/tables
```

- MRR/MAP/nDCG@10 and structural metrics: **exact**
- Outcome/rubric/fidelity: within ±0.02 (manifest tolerance bands)

## 5. Inspect outputs

```text
reports/repro-paper-v1.0/tables/
├── headline.csv          # all variants × metrics
├── by_profile.csv        # inspiration_profile strata
├── variant_delta.csv     # graph-full vs baselines/ablations
└── trajectory_audit.csv  # excluded incomplete/degraded
```

## CI smoke (≤20 items, ≤15 min)

```bash
uv run pytest tests/integration/test_repro_smoke.py -q
```

Uses `releases/paper-smoke/manifest.yaml` (all five variants, ≤20 items), `USE_MOCK_JUDGE=1`, `USE_MOCK_LLM=1`, fixture bundle subset.

## Troubleshooting

| Issue | Action |
|-------|--------|
| LFS object missing | `git lfs pull --include="data/benchmarks/custom-judge/**"` |
| Relevance gate fails | Read `relevance_report.json`; fix unresolved `expected_section_paths` |
| EDGAR network during eval | Ensure `OFFLINE_BENCHMARK=1`; corpus must be bundled |
| Embedding model download | Pre-build cache: `repro run --variants flat-chunk --max-items 1` once online; cache ships in bundle for paper tag |
| Judge API errors | Degraded runs excluded from headline; see `trajectory_audit.csv` |

## What this kit does NOT run

Headline tables do **not** invoke FinDER, FinanceBench, or FinAgentBench registry adapters. Inspiration profile names label task families within **custom-judge** only.

## Related docs

- Dataset generation: `docs/custom-judge-dataset-generation.md`
- Legacy benchmark notes: `docs/benchmark-reproduction.md` (superseded by this quickstart for paper-v1.0)
