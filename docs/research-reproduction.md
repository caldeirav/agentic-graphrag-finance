# Research Reproduction Guide

End-to-end walkthrough for reproducing **Graph-Grounded Agentic Retrieval** paper benchmark tables on the **custom-judge** evaluation dataset (features **012** + **013**).

| Feature | What it adds |
|---------|----------------|
| **012** | Five variants, frozen corpus, table export, release manifests |
| **013** | `--defer-judge`, `judge-batch`, per-item graph slices, `--resume` checkpoints |

For dataset generation (building custom-judge), see [custom-judge-dataset-generation.md](custom-judge-dataset-generation.md). Operator quickstarts: [012 quickstart](../specs/012-research-repro-kit/quickstart.md) · [013 quickstart](../specs/013-benchmark-eval-acceleration/quickstart.md).

## How live EDGAR, live judge, and offline eval fit together

Research reproduction is a **two-phase** pipeline:

| Phase | Command | Network | Purpose |
|-------|---------|---------|---------|
| **1 — Corpus build** | `agent-query benchmark-dataset generate` | **Live SEC EDGAR** + Gemini (item authoring) | Fetch filings, parse XBRL/HTML, build graph snapshots, write Q&A items into a draft bundle |
| **2 — Paper eval** | `agent-query repro run-all` | **Live Gemini judge** + **live agent LLM** (LM Studio for graph variants) + **MiniLM** (flat-chunk only); **no EDGAR** | Run five variants on the **frozen** bundled corpus; export paper tables |

Phase 2 sets `OFFLINE_BENCHMARK=1` so evaluation never re-fetches EDGAR — it reads the corpus produced in phase 1 (or a published LFS bundle at `paper-v1.0`). That offline gate is intentional: paper tables compare systems on an identical frozen corpus.

**Live components for real paper reproduction:**

- **Live EDGAR** — phase 1 only (`SEC_EDGAR_USER_AGENT` in `.env`; do **not** set `USE_FIXTURE_INGESTION=1`)
- **Live Gemini judge** — phase 2 scoring (`GOOGLE_API_KEY`, `USE_MOCK_JUDGE=0`)
- **Live agent LLM** — phase 2 `graph-full` and ablation variants only (`USE_MOCK_LLM=0`, LM Studio running)
- **MiniLM embeddings** — phase 2 `flat-chunk` variant only (`uv sync --extra reproduction`; local CPU, no LM Studio)

**CI / fixture path** (`releases/paper-smoke`, `USE_MOCK_JUDGE=1`, `USE_MOCK_LLM=1`) validates wiring only — not headline paper numbers.

## What this reproduces

At release tag `paper-v1.0`, the kit runs **five system variants** on the full published **custom-judge `dev` split** (≥200 items):

| Variant | Description |
|---------|-------------|
| `graph-full` | Production graph-grounded agent |
| `flat-chunk` | Dense embedding RAG (no graph navigation) |
| `ablation-no-macro` | Pre-bound filings only (no macro router) |
| `ablation-no-walker` | No meso/micro graph walker hops |
| `ablation-xbrl-only` | Excludes HTML narrative chunks |

### Models used in phase 2

Phase 2 runs three different model roles. Do not conflate them:

| Model | Used by | Role |
|-------|---------|------|
| **LM Studio / Qwen** (local LLM) | `graph-full`, all ablations | Agent routing (macro, intent, meso, micro) and grounded answer synthesis |
| **Gemini** (judge) | **All five variants** | Scores answers, rubrics, and trajectories — same judge for fair comparison |
| **MiniLM** (`sentence-transformers/all-MiniLM-L6-v2`) | **`flat-chunk` only** | Dense retrieval baseline — see below |

**What MiniLM does (and does not do):**

MiniLM is a small, local **embedding** model. It is **not** the agent that answers questions and **not** the judge. It exists only to power the **`flat-chunk` comparison baseline** in paper reproduction:

1. Take the same frozen evidence chunks as the graph agent (paragraphs, XBRL facts, tables from the bundled graph).
2. Embed the benchmark question and every chunk into vectors (384 dimensions).
3. Rank chunks by cosine similarity and return the top-k — no graph navigation, no filing/section routing.
4. Stitch those chunk excerpts into a simple retrieval-only answer, which **Gemini** then scores like any other variant.

That gives the paper a standard dense RAG baseline on identical items and corpus, so `variant_delta.csv` can show **graph-full minus flat-chunk** (e.g. nDCG@10, outcome accuracy).

Install with `uv sync --extra reproduction` (pulls `sentence-transformers`). First `flat-chunk` run downloads MiniLM (~90 MB) and caches chunk vectors under `{bundle}/corpus/chunk_embeddings/`. Runs on CPU; LM Studio is **not** required for `flat-chunk`.

Outputs: `headline.csv`, `by_profile.csv`, `variant_delta.csv`, `trajectory_audit.csv` under `reports/repro-{tag}/tables/`.

Headline tables use **custom-judge only** — not upstream FinDER/FinanceBench/FinAgentBench adapters.

## Prerequisites

```bash
uv sync --locked
uv sync --locked --extra reproduction   # sentence-transformers for flat-chunk variant
```

`.env` (minimum for **live** reproduction):

```bash
SEC_EDGAR_USER_AGENT=Your Name your.email@example.com   # phase 1 only
GOOGLE_API_KEY=...                                       # phase 1 generate + phase 2 judge
USE_MOCK_JUDGE=0
USE_MOCK_LLM=0
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3.6-35b-a3b
```

Start **LM Studio** and load the pinned model before phase 2.

For published `paper-v1.0` (skip phase 1 if bundle already published):

```bash
git lfs pull --include="data/benchmarks/custom-judge/v1.0.0/corpus/**"
```

### Environment summary

| Variable | Phase 1 (generate) | Phase 2 (repro eval) | CI smoke |
|----------|-------------------|----------------------|----------|
| `SEC_EDGAR_USER_AGENT` | **Required** | Not used | Not used |
| `USE_FIXTURE_INGESTION=1` | **Do not set** (live EDGAR) | Not used | CI generate only |
| `GOOGLE_API_KEY` | **Required** (item authoring) | **Required** (eval judge) | Not required |
| `USE_MOCK_JUDGE=0` | Recommended live | **Required** for `paper-v1.0` / `paper-live-smoke` | `1` |
| `USE_MOCK_LLM=0` | N/A (materialize uses production path) | **Required** for live repro | `1` |
| `OFFLINE_BENCHMARK=1` | **Do not set** | **Required** | **Required** |

Reference machine (documented target): 8 vCPU, 32 GB RAM, ~2–4 GB LFS pre-pulled; ≤8 h wall-clock for full `paper-v1.0` with live judge.

---

## Live end-to-end verification (small sample)

Use this to confirm the **full** pipeline (live EDGAR → frozen bundle → live judge + LLM → five variants → tables) on **2 items** before committing to a full `paper-v1.0` run.

### Step 1 — Build draft bundle from live EDGAR

```bash
# Live EDGAR + Gemini; writes data/benchmarks/custom-judge/drafts/live-repro-smoke/
uv run agent-query benchmark-dataset generate \
  -c configs/benchmarks/custom_judge_live.yaml \
  --run-id live-repro-smoke \
  --target-items 2 \
  --trace verbose
```

Requires `SEC_EDGAR_USER_AGENT` and `GOOGLE_API_KEY`. Do **not** set `USE_FIXTURE_INGESTION` or `OFFLINE_BENCHMARK`.

Inspect `data/benchmarks/custom-judge/drafts/live-repro-smoke/generation_report.json` and `items/dev.jsonl`.

### Step 2 — Run reproduction (live judge + LLM, offline corpus)

```bash
export OFFLINE_BENCHMARK=1
export USE_MOCK_JUDGE=0
export USE_MOCK_LLM=0
# GOOGLE_API_KEY and LM Studio must be available

uv run agent-query repro run-all \
  --manifest releases/paper-live-smoke/manifest.yaml \
  --output reports/repro-live-smoke \
  --max-items 2
```

This runs: verify corpus (hashes from draft `manifest.json`) → materialize relevance labels → **five variants** → table export → `repro_run.json`.

Expected outputs:

```text
reports/repro-live-smoke/
├── repro_run.json
├── graph-full/benchmark-*/summary.json
├── flat-chunk/...
├── ablation-no-macro/...
├── ablation-no-walker/...
├── ablation-xbrl-only/...
└── tables/
    ├── headline.csv
    ├── by_profile.csv
    ├── variant_delta.csv
    ├── trajectory_audit.csv
    └── headline.tex
```

Wall-clock: roughly **5–15 minutes** for 2 items × 5 variants with live judge (depends on Gemini + LM Studio latency).

### Step 3 — Spot-check results

```bash
head reports/repro-live-smoke/tables/headline.csv
cat reports/repro-live-smoke/repro_run.json
```

Confirm `judge_status` is not uniformly `degraded` in variant summaries and that `trajectory_audit.csv` lists included headline items.

---

## CI smoke (fixtures only, no live EDGAR or judge)

Uses `releases/paper-smoke/manifest.yaml` and `tests/fixtures/custom_judge/`:

```bash
export OFFLINE_BENCHMARK=1
export USE_MOCK_JUDGE=1
export USE_MOCK_LLM=1

uv run agent-query repro run-all \
  --manifest releases/paper-smoke/manifest.yaml \
  --output reports/repro-paper-smoke \
  --max-items 3 \
  --skip-relevance
```

Or: `uv run pytest tests/integration/test_repro_smoke.py -q`

---

## Full paper reproduction (`paper-v1.0`)

### 1. Checkout release and pull corpus

```bash
git checkout paper-v1.0    # when published
git lfs pull --include="data/benchmarks/custom-judge/v1.0.0/corpus/**"
```

Release manifest: `releases/paper-v1.0/manifest.yaml` pins **corpus content hashes**, **items hash**, and **relevance label hash** (plus judge/LLM/embedding config paths). `git_sha` is an optional provenance note only — repro does not require checking out a specific commit unless you pass `--strict-git`.

### 2. Verify frozen corpus

```bash
export OFFLINE_BENCHMARK=1

uv run agent-query repro verify-corpus \
  --manifest releases/paper-v1.0/manifest.yaml
```

Fails fast on missing LFS objects or hash mismatch.

### 3. Materialize graph-grounded relevance labels

Required if the published bundle lacks `relevance_labels_hash` or coverage &lt; 90%:

```bash
uv run agent-query repro materialize-relevance \
  --manifest releases/paper-v1.0/manifest.yaml
```

Derives `relevant_chunk_ids` from chunk nodes under each item's `expected_section_path`. Gate: ≥90% items labeled.

### 4. Run all variants and export tables (live judge + LLM)

**Recommended (013):** defer judging and enable resume so generation and Gemini scoring are decoupled and interruptible.

```bash
export OFFLINE_BENCHMARK=1
export USE_MOCK_JUDGE=0
export USE_MOCK_LLM=0

uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --defer-judge \
  --resume
```

Equivalent env toggle: `REPRO_DEFER_JUDGE=1` instead of `--defer-judge`. Optional: `REPRO_JUDGE_CONCURRENCY=2` (default) for parallel judge-batch calls.

**Classic (012 inline judge):** omit `--defer-judge` — Gemini runs after every item during generation (slower, harder to resume mid-variant).

No `--max-items` on `paper-v1.0` (full `dev` split). Live judge and LLM are **enforced** for this release tag when defer is off.

### 5. Verify against release checksums

```bash
uv run agent-query repro verify-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0/tables
```

- **MRR / MAP / nDCG@10 / structural metrics**: exact match
- **Outcome / rubric / trajectory fidelity**: within ±0.02 tolerance bands in manifest

## CLI reference

| Command | Purpose |
|---------|---------|
| `benchmark-dataset generate` | Phase 1: live EDGAR corpus + Gemini items |
| `repro verify-corpus` | Hash-check bundled corpus |
| `repro materialize-relevance` | Derive `relevant_chunk_ids` |
| `repro run` | Run selected variants |
| `repro run-all` | Full phase-2 workflow (recommended) |
| `repro run-all --defer-judge` | Generation without per-item Gemini; judge-batch after each variant |
| `repro judge-batch` | Score pending items in existing `results.json` (idempotent v2 resume; `--force-rescore`) |
| `repro run-all --judge-only` | Judge batch only (skip agent generation) |
| `repro run-all --export-only` | Export tables from checkpoints |
| `repro run-all --resume/--no-resume` | Resume partial runs (default: resume) |
| `repro verify-tables` | Compare exports to expected checksums |
| `repro report` | Static HTML investigation report + LaTeX/CSV/Markdown table copy (014) |

```bash
uv run agent-query repro --help
```

## Results viewer (014)

After phase 2 completes, generate a read-only HTML report for run investigation and arXiv table copy:

```bash
uv run agent-query repro report \
  --input reports/repro-live-smoke \
  --output reports/repro-live-smoke/report.html

# Paste-ready headline table for LaTeX manuscripts:
uv run agent-query repro report \
  --input reports/repro-live-smoke \
  --format latex-only --table headline
```

The report consumes existing artifacts only (`repro_run.json`, `tables/*.csv`, optional `{variant}/results.json`); it does not re-run agents or judges. Investigation notes are aggregated (≤25 per run). Optional stratified tables: `by_evidence_source.csv`, `variant_delta_by_source.csv`. Operator quickstart: [014 quickstart](../specs/014-repro-results-viewer/quickstart.md) | [015 quickstart](../specs/015-repro-eval-validity/quickstart.md). Troubleshooting partial runs: missing variant checkpoints produce warnings, not hard failures.

## Fair outcome scoring (016)

Feature **016** corrects reproduction outcome scoring and publishes custom-judge bundle **v1.1.0**:

| Change | Effect |
|--------|--------|
| **Outcome policy** | Answer-GT `outcome_accuracy` uses `value_alignment` only (missing → 0.0); no `synthesis_grounding` fallback |
| **Judge v3** | Variant-aware criteria; resume skips only v3-complete verdicts |
| **Bundle v1.1.0** | Rubric routing, `required_claims` on narrative answers, binding feasibility gates |
| **Report** | Outcome-by-profile and outcome-by-stratum sections; `OUTCOME_ORDERING_REGRESSION` when SC-001 fails |

Release manifest `releases/paper-v1.0/manifest.yaml` points at `data/benchmarks/custom-judge/v1.1.0`. Migrate from v1.0.0 with `evaluation.generation.migrate_v1_1_0.build_draft_from_parent`, then publish. Items flagged `requires_agent_rerun: true` in `CHANGELOG.md` need a selective agent re-run before citing new rubric routes.

### v3 re-judge workflow

Re-score existing checkpoints without re-running agents (all variants need v3 verdicts):

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --force-rescore

uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0

uv run agent-query repro report \
  --input reports/repro-paper-v1.0 \
  --output reports/repro-paper-v1.0/report.html
```

Resume without `--force-rescore` skips only items with complete v3 criteria. `export_manifest.json` records `min_judge_version: v3` and `outcome_scoring_policy: value_alignment_only`. Operator quickstart: [016 quickstart](../specs/016-fair-outcome-scoring/quickstart.md).

If headline `outcome_accuracy` remains low (~0.14) after v3 re-score on v1.1.0, that reflects retrieval failure on the 61-item answer-GT pool (not synthesis fallback). Follow the **[v1.2.0 migration checklist](../specs/016-fair-outcome-scoring/checklists/v1.2.0-migration.md)** for dataset, agent, judge, and full-repro phases targeting **0.45–0.60** graph-full outcome.

## Bundle v2.0 and paper-v2.0 (017)

Custom-judge **v2.0.0** is a net-new 200-item dev split with **100% answer-GT**, quota-balanced profiles (~68 / 66 / 66), and ≥40 multi-filing `comparison_structured` items. Generation details: [custom-judge-dataset-generation.md § Bundle v2.0](custom-judge-dataset-generation.md#bundle-v20-net-new-pool).

Published bundle: `data/benchmarks/custom-judge/v2.0.0/`. Release lock: `releases/paper-v2.0/manifest.yaml` verifies **corpus**, **items**, and **relevance** hashes — not git HEAD. Use `--no-resume` and a fresh `--output` dir when re-running after code or bundle fixes.

### Full paper-v2.0 reproduction

```bash
git lfs pull --include="data/benchmarks/custom-judge/v2.0.0/corpus/**"
export OFFLINE_BENCHMARK=1 USE_MOCK_LLM=0 USE_MOCK_JUDGE=0

uv run agent-query repro run-all \
  --manifest releases/paper-v2.0/manifest.yaml \
  --output reports/repro-paper-v2.0 \
  --defer-judge --resume

uv run agent-query repro export-tables \
  --manifest releases/paper-v2.0/manifest.yaml \
  --input reports/repro-paper-v2.0

uv run agent-query repro report --input reports/repro-paper-v2.0
```

**v2 headline semantics**: `task_success` = mean value_alignment over n=200; no `rubric_alignment` row in exports. Judge v3.1 + `required_claims` on all items.

### Path-repair v2 + clean re-run protocol

After v1 `repair-bundle` mis-mapped divestiture items to Item 1 Business, run **v2 repair** then a **fresh repro** (never `--resume` against a pre-fix checkpoint):

```bash
# 1. Re-map divestiture / narrative items → MD&A or 10-Q; rematerialize relevance
uv run agent-query benchmark-dataset repair-bundle \
  data/benchmarks/custom-judge/v2.0.0 \
  --repair-version v2

# 2. Update manifest pins from bundle (items_hash, relevance_labels_hash)
uv run python -c "
from pathlib import Path
from evaluation.generation.bundle import items_hash
import json, yaml
root = Path('data/benchmarks/custom-judge/v2.0.0')
rel = json.loads((root / 'relevance_labels.json').read_text())
manifest = yaml.safe_load(Path('releases/paper-v2.0/manifest.yaml').read_text())
manifest['items_hash'] = items_hash(root / 'items/dev.jsonl')
manifest['relevance_labels_hash'] = rel['labels_hash']
Path('releases/paper-v2.0/manifest.yaml').write_text(yaml.safe_dump(manifest, sort_keys=False))
print('items_hash', manifest['items_hash'])
print('relevance_labels_hash', manifest['relevance_labels_hash'])
"

# 3. Verify frozen bundle + pins
uv run agent-query repro verify-corpus \
  --manifest releases/paper-v2.0/manifest.yaml

# 4. Full repro on a NEW output directory (no --resume)
uv run agent-query repro run-all \
  --manifest releases/paper-v2.0/manifest.yaml \
  --output reports/repro-paper-v2.0-v2repair \
  --defer-judge --no-resume

# 5. Report + tables
uv run agent-query repro report \
  --input reports/repro-paper-v2.0-v2repair \
  --manifest releases/paper-v2.0/manifest.yaml \
  --output reports/repro-paper-v2.0-v2repair/report.html
```

Repaired items carry `suppress_benchmark_path_injection: true` so meso routing uses TOC/heuristics instead of forced `expected_section_paths` injection. Compare against the prior run only after both use the **same** bundle hashes.

Operator quickstart: [017 quickstart](../specs/017-custom-judge-v2/quickstart.md).

## Output layout

```text
reports/repro-paper-v1.0/
├── repro_run.json
├── graph-full/benchmark-*/summary.json
├── flat-chunk/...
├── ablation-no-macro/...
├── ablation-no-walker/...
├── ablation-xbrl-only/...
└── tables/
    ├── headline.csv
    ├── by_profile.csv
    ├── variant_delta.csv
    ├── trajectory_audit.csv
    ├── by_evidence_source.csv      # optional (015)
    └── variant_delta_by_source.csv # optional (015)
```

## Recovery playbook (013)

Long `paper-v1.0` runs can be interrupted. Checkpoints live under `reports/repro-paper-v1.0/`.

1. **Check progress**: `jq length reports/repro-paper-v1.0/graph-full/results.json` and `cat reports/repro-paper-v1.0/repro_run.json`
2. **Resume generation** (default): re-run the same `repro run-all` command with `--defer-judge` if used initially; completed `item_id` rows are skipped
3. **Judge only** (defer mode):

   ```bash
   uv run agent-query repro judge-batch \
     --manifest releases/paper-v1.0/manifest.yaml \
     --input reports/repro-paper-v1.0
   ```

   Or: `repro run-all ... --judge-only` with the same manifest and output directory.
4. **Export only**: `uv run agent-query repro run-all --manifest releases/paper-v1.0/manifest.yaml --output reports/repro-paper-v1.0 --export-only`
5. **Reset one variant**: `rm -rf reports/repro-paper-v1.0/graph-full` and remove that variant from `completed_variants` in `repro_run.json`, or use `--no-resume` on a fresh `--output` directory

**Faster eval (013)**: use `--defer-judge` (or `REPRO_DEFER_JUDGE=1`) to batch Gemini judging after each variant; `REPRO_JUDGE_CONCURRENCY=2` controls judge-batch parallelism. Per-item graph scope loads only issuers from `expected_bindings` (smaller graphs, faster agent runs).

## Troubleshooting

| Issue | Action |
|-------|--------|
| LFS object missing | `git lfs pull --include="data/benchmarks/custom-judge/**"` |
| Draft bundle missing for `paper-live-smoke` | Run step 1 with `--run-id live-repro-smoke` |
| `Bundled graph snapshot missing: ...graphml` | Bug fixed in materialize (012): re-run phase-1 `generate`, or copy `data/graphs/{TICKER}/{snapshot_id}.graphml` (+ `.manifest.json`) into `{draft}/corpus/graphs/{TICKER}/` |
| `requires live Gemini judge` error | Unset `USE_MOCK_JUDGE` / set `USE_MOCK_JUDGE=0`; set `GOOGLE_API_KEY` |
| `requires live agent LLM` error | Start LM Studio; set `USE_MOCK_LLM=0` |
| Relevance gate fails | Inspect `relevance_report.json` in bundle root |
| EDGAR network during **eval** | Ensure `OFFLINE_BENCHMARK=1` (eval must use frozen bundle) |
| EDGAR errors during **generate** | Check `SEC_EDGAR_USER_AGENT`; unset `USE_FIXTURE_INGESTION` |
| Embedding model download | `uv sync --extra reproduction`; first `flat-chunk` run downloads MiniLM and caches vectors under the bundle |
| LM Studio not needed for flat-chunk | MiniLM runs on CPU; only graph-full and ablations call LM Studio |

## Design references

- Spec: [012](../specs/012-research-repro-kit/spec.md) · [013](../specs/013-benchmark-eval-acceleration/spec.md)
- Quickstart: [012](../specs/012-research-repro-kit/quickstart.md) · [013](../specs/013-benchmark-eval-acceleration/quickstart.md)
- Variant configs: `configs/reproduction/variants/`
- Item subgraph contract: [contracts/item-subgraph.md](../specs/013-benchmark-eval-acceleration/contracts/item-subgraph.md)
