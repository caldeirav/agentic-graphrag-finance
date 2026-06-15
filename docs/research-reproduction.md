# Research Reproduction Guide

Reproduce the **paper-v1.0** benchmark tables: five system variants on the published **custom-judge v2.0.0** dev split (200 items, 100% answer ground truth).

**Baseline run:** `reports/repro-paper-v1.0/` (local; gitignored). Frozen headline metrics: `releases/paper-v1.0/expected_checksums.json`.

**Dataset generation:** [custom-judge-dataset-generation.md](custom-judge-dataset-generation.md) · **Spec:** [017](../specs/017-custom-judge-v2/spec.md)

---

## What you reproduce

| Variant | Description |
|---------|-------------|
| `graph-full` | Production graph-grounded agent (baseline) |
| `flat-chunk` | Dense embedding RAG (MiniLM; no graph navigation) |
| `ablation-no-macro` | Pre-bound filings only (no macro router) |
| `ablation-no-walker` | No meso/micro graph walker hops |
| `ablation-xbrl-only` | Excludes HTML narrative chunks |

**Headline metric:** `task_success` = mean `value_alignment` over n=200 (missing scores count as 0). No `rubric_alignment` row in exports.

**Baseline numbers (graph-full, lock repro):** `task_success` ≈ 0.467 · `mrr` ≈ 0.916 · `nDCG@10` ≈ 0.631

---

## Two-phase pipeline

| Phase | Command | Network | Purpose |
|-------|---------|---------|---------|
| **1 — Corpus + items** | `benchmark-dataset generate` → `publish` | Live EDGAR + Gemini | Build and publish `data/benchmarks/custom-judge/v2.0.0/` |
| **2 — Paper eval** | `repro run-all` | Live Gemini judge + LM Studio (graph variants) + MiniLM (`flat-chunk` only); **no EDGAR** | Five variants on frozen bundle; export tables |

Phase 2 requires `OFFLINE_BENCHMARK=1`. The published bundle is already on disk after `git lfs pull`; you normally **skip phase 1** unless regenerating the dataset.

### Models in phase 2

| Model | Used by | Role |
|-------|---------|------|
| **LM Studio / Qwen** | `graph-full`, ablations | Agent routing and synthesis |
| **Gemini** | All five variants | External judge (value alignment, trajectory) |
| **MiniLM** | `flat-chunk` only | Dense retrieval baseline (`uv sync --extra reproduction`) |

---

## Prerequisites

```bash
uv sync --locked
uv sync --locked --extra reproduction   # flat-chunk embeddings
git lfs pull --include="data/benchmarks/custom-judge/v2.0.0/corpus/**"
```

`.env` for live reproduction:

```bash
GOOGLE_API_KEY=...
USE_MOCK_JUDGE=0
USE_MOCK_LLM=0
LM_STUDIO_BASE_URL=http://localhost:1234/v1
```

Start **LM Studio** before phase 2 graph variants.

---

## Reproduce paper-v1.0 (canonical workflow)

```bash
export OFFLINE_BENCHMARK=1 USE_MOCK_JUDGE=0 USE_MOCK_LLM=0

# 1. Verify frozen corpus hashes
uv run agent-query repro verify-corpus \
  --manifest releases/paper-v1.0/manifest.yaml

# 2. Full reproduction (5 variants × 200 items; ~8h+ wall-clock)
uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --defer-judge --no-resume

# 3. Verify tables against frozen baseline
uv run agent-query repro verify-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

# 4. Investigation report + LaTeX copy
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0/report.html
```

Use `--resume` instead of `--no-resume` to continue an interrupted run (same `--output` directory).

### Compare to the committed baseline

If your re-run matches the lock repro within tolerance bands in the manifest, `verify-tables` passes. Ranking metrics (MRR, MAP, nDCG@10) must match exactly; `task_success` and `trajectory_fidelity` allow ±0.02.

---

## Output layout

```text
reports/repro-paper-v1.0/
├── repro_run.json
├── export_manifest.json
├── report.html                         # from repro report
├── graph-full/results.json
├── flat-chunk/results.json
├── ablation-no-macro/results.json
├── ablation-no-walker/results.json
├── ablation-xbrl-only/results.json
└── tables/
    ├── headline.csv
    ├── headline.tex
    ├── by_profile.csv
    ├── variant_delta.csv
    ├── trajectory_audit.csv
    ├── by_evidence_source.csv
    └── variant_delta_by_source.csv
```

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `repro verify-corpus` | Hash-check bundled corpus against manifest |
| `repro materialize-relevance` | Derive `relevant_chunk_ids` (if labels missing) |
| `repro run-all` | Verify → relevance → all variants → export tables |
| `repro run-all --defer-judge` | Batch Gemini judging after each variant (recommended) |
| `repro judge-batch` | Score pending items in `results.json` |
| `repro run-all --judge-only` | Judge phase only |
| `repro run-all --export-only` | Rebuild tables from checkpoints |
| `repro verify-tables` | Compare exports to `expected_checksums.json` |
| `repro report` | HTML report + LaTeX/CSV/Markdown copy |

```bash
uv run agent-query repro --help
```

---

## Results report (014)

The HTML report is read-only over existing artifacts:

| Section | Contents |
|---------|----------|
| By evidence source | `variant_id` × `primary_evidence_source` rows; all metrics as columns |
| Variant comparison | Headline metrics pivoted (baseline `graph-full`) |
| Investigation notes | Aggregated checks (e.g. ordering regressions, zero-citation patterns) |
| Item drill-down | One row per item; variants side-by-side; full Q/A + judge detail |

```bash
uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --format latex-only --table headline
```

Quickstart: [014](../specs/014-repro-results-viewer/quickstart.md)

---

## Recovery

1. **Check progress:** `jq length reports/repro-paper-v1.0/graph-full/results.json`
2. **Resume:** re-run the same `run-all` command with `--defer-judge --resume`
3. **Judge only:** `repro run-all ... --judge-only` or `repro judge-batch --input reports/repro-paper-v1.0`
4. **Export only:** `repro run-all ... --export-only`
5. **Fresh run:** `--no-resume` on a new `--output` directory

---

## CI wiring check (fixtures only)

Not for paper numbers — validates CLI wiring with mocks:

```bash
export OFFLINE_BENCHMARK=1 USE_MOCK_JUDGE=1 USE_MOCK_LLM=1
uv run agent-query repro run-all \
  --manifest releases/paper-smoke/manifest.yaml \
  --output reports/repro-paper-smoke \
  --max-items 3 --skip-relevance
```

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| LFS object missing | `git lfs pull --include="data/benchmarks/custom-judge/v2.0.0/**"` |
| `requires live Gemini judge` | `USE_MOCK_JUDGE=0` and `GOOGLE_API_KEY` set |
| `requires live agent LLM` | Start LM Studio; `USE_MOCK_LLM=0` |
| `verify-tables` fails | Compare `headline.csv` to baseline; check code or bundle hash drift |
| EDGAR during eval | Set `OFFLINE_BENCHMARK=1` |
| Embedding download | `uv sync --extra reproduction`; first `flat-chunk` run caches MiniLM vectors |

---

## Design references

- Release manifest: `releases/paper-v1.0/manifest.yaml`
- Bundle: `data/benchmarks/custom-judge/v2.0.0/`
- Variant configs: `configs/reproduction/variants/`
- Specs: [012](../specs/012-research-repro-kit/spec.md) · [013](../specs/013-benchmark-eval-acceleration/spec.md) · [017](../specs/017-custom-judge-v2/spec.md)
