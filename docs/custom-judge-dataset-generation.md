This guide describes how the project builds the **custom-judge v2.0.0** evaluation benchmark from live SEC EDGAR filings—the frozen dataset behind **`paper-v1.0`** reproduction.

The pipeline samples issuers, materializes XBRL/graph snapshots through the same production path as `agent-query ask`, uses **Gemini** to author grounded Q&A items, validates them against the bundled graph index, and writes a reproducible draft bundle for operator publish.

**Published bundle:** `data/benchmarks/custom-judge/v2.0.0/` · **Release lock:** `releases/paper-v1.0/manifest.yaml`

Question **style and taxonomy** are inspired by FinanceBench, FinDER, and FinAgentBench. Generated items are **native to this project's SEC/XBRL corpus**—we do not bulk-import upstream benchmark rows.

**Paper reproduction (phase 2):** [research-reproduction.md](research-reproduction.md)

---

## Design references (papers and datasets)

The `custom-judge` pipeline uses upstream work as **inspiration profiles** (prompt templates + validation rules), not as a source of copied questions. Each profile maps to a published benchmark family:

| Inspiration profile | Upstream benchmark | Paper | Dataset / code |
|---------------------|-------------------|-------|----------------|
| `financebench` | **FinanceBench** — metrics, domain-relevant, and novel-generated QA over financial disclosures | [Isenberg et al., arXiv:2311.11944](https://arxiv.org/abs/2311.11944) | [patronus-ai/financebench](https://github.com/patronus-ai/financebench) |
| `finder` | **FinDER** — retrieval QA with evidence rubrics for financial document retrieval | [Linq-AI-Research, arXiv:2504.15800](https://arxiv.org/abs/2504.15800) | [Hugging Face: Linq-AI-Research/FinDER](https://huggingface.co/datasets/Linq-AI-Research/FinDER) |
| `finagentbench` | **FinAgentBench** — agentic multi-hop retrieval across multiple filings | [arXiv:2508.14052](https://arxiv.org/abs/2508.14052) | [Kaggle: ACM ICAIF '25 Agentic Retrieval Grand Challenge](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data) |

### How each reference shapes generation

| Profile | Borrowed from upstream | Adapted for this project |
|---------|------------------------|---------------------------|
| **FinanceBench** | Question-type taxonomy (`metrics-generated`, `domain-relevant`, `novel-generated`); short numeric or textual gold answers | Items bind to **graph-resolvable** `expected_section_paths` (`{accession}/{section_slug}`) instead of PDF page numbers |
| **FinDER** | Retrieval-focused questions; rubric-based scoring | Answer-GT required; `required_claims` on narrative answers |
| **FinAgentBench** | Multi-hop, cross-filing agentic tasks | `expected_bindings.accessions` must span **≥2 filings**; v2 uses `answer_type: comparison_structured` with per-filing + cross-filing `required_claims` |

Prompt templates: `configs/benchmarks/inspiration_profiles/{financebench,finder,finagentbench}.yaml`.  
Profile mix is **config-only** (`profile_quotas` in YAML); v1 defaults to ~equal thirds (~34% / 33% / 33%).

For design rationale and boundary decisions, see [research.md §R4](../specs/011-judge-eval-dataset/research.md#r4--inspiration-profile-prompts-financebench--finder--finagentbench).

---

## Goals

| Goal | How |
|------|-----|
| Grounded items | Every item binds to real accessions and resolvable `expected_section_paths` from the materialized graph |
| Reproducible sampling | Committed allowlist + `random_seed` → deterministic `sampling_manifest.json` hash |
| Production-faithful corpus | Materialization calls `cli.corpus_pipeline.run_materialize_pipeline` (Docling/XBRL + docling-graph) |
| Style diversity | Three **inspiration profiles** aligned to [FinanceBench](https://arxiv.org/abs/2311.11944), [FinDER](https://arxiv.org/abs/2504.15800), and [FinAgentBench](https://arxiv.org/abs/2508.14052) taxonomies |
| Offline evaluation | Published bundle includes frozen corpus (Git LFS); eval runs refuse live EDGAR when `OFFLINE_BENCHMARK=1` |
| Audit trail | Draft manifests, generation reports, and checkpoint files support review before `publish` |

The registry name for the resulting dataset is **`custom-judge`**.

---

## End-to-end flow

```mermaid
flowchart LR
  A[GenerationConfig YAML] --> B[Sampling]
  B --> C[Materialize]
  C --> D[Judge generate]
  D --> E[Validate + dedup]
  E --> F[Draft bundle]
  F --> G[Operator publish]
  G --> H[Registry custom-judge]

  B --> B1[sampling_manifest.json]
  C --> C1[corpus/ + graph_node_index.json]
  D --> D1[Gemini item JSON]
  E --> E1[items/dev_pool.jsonl]
  E1 --> E2[profile-balanced selection]
  E2 --> E3[items/dev.jsonl]
  F --> F1[manifest.json + generation_report.json]
```

**v2.0** keeps the full accepted pool in `items/dev_pool.jsonl`, then selects a **quota-balanced** 200-item dev split (see [Published bundle structure](#published-bundle-structure)).

### Phase 1 — Sampling

1. Load `GenerationConfig` and committed **issuer allowlist** (hash verified).
2. Build an **accession catalog** per ticker (live EDGAR `list_recent_filings` by default; fixture catalog only when `USE_FIXTURE_INGESTION=1`).
3. Seed-random draw of issuers and filings subject to `filing_filters` and governance caps.
4. Write `sampling_manifest.json` (config hash, allowlist hash, selected accessions).

**Module:** `src/evaluation/generation/sampler.py`  
**CLI catalog:** `src/cli/benchmark_catalog.py`

### Phase 2 — Materialize

1. For each sampled issuer, build a `CorpusDefinition` with **explicit accessions** from the sampling manifest.
2. Invoke `run_materialize_pipeline` (fetch → parse → graph build).
3. Copy graph snapshots into the draft `corpus/` tree and export `corpus/graph_node_index.json` for validation.
4. Write `corpus_bundle.json` and update `generation_report.json` with ingestion failures (if any).

**Module:** `src/cli/benchmark_materialize.py` (CLI facade; evaluation layer must not import ingestion directly).

### Phase 3 — Judge generate + validate

1. Schedule inspiration profiles per `profile_quotas` (v1 default: equal thirds; smoke configs may use 50/50).
2. For each candidate, call **Gemini** (`GeminiItemGenerator`) with profile-specific prompts styled after FinanceBench, FinDER, and FinAgentBench (see [Design references](#design-references-papers-and-datasets)).
3. **Validate** each item: non-empty question, ground truth or rubric, accessions ⊆ snapshot, every section path ∈ graph index; profile-specific rules (e.g. FinAgentBench ≥2 filings).
4. **Deduplicate** near-duplicate questions (similarity threshold from governance config).
5. **v2 only**: write all unique accepts to `items/dev_pool.jsonl`, then **profile-balanced selection** into `items/dev.jsonl` (200 items matching `profile_quotas`).
6. Write all candidates to `candidates.jsonl`, finalize `manifest.json` (`status: draft`).

**v2 post-parse normalization** (`v2_item_normalize.py`): infer `answer_type`, derive or repair `required_claims`. Comparison items validate **semantic** cross-filing synthesis (per-filing claims + a natural-language compare/contrast claim), not fixed boilerplate phrases.

**Modules:** `src/evaluation/generation/judge_generator.py`, `gemini_item_generator.py`, `item_validator.py`, `deduplicator.py`, `bundle.py`

Mock mode (`USE_MOCK_JUDGE=1` + `custom_judge_ci` config) skips Gemini for CI.

---

## Inspiration profiles

Prompt templates live under `configs/benchmarks/inspiration_profiles/`. See [Design references](#design-references-papers-and-datasets) for papers and upstream datasets.

| Profile | Upstream | Style | Typical ground truth | Filing count |
|---------|----------|-------|---------------------|--------------|
| `financebench` | [FinanceBench](https://github.com/patronus-ai/financebench) | Metrics, domain, novel generated | `ground_truth.answer` | Single-filing |
| `finder` | [FinDER](https://huggingface.co/datasets/Linq-AI-Research/FinDER) | Retrieval QA | v1: rubric primary; **v2: `ground_truth.answer` required** | Single-filing |
| `finagentbench` | [FinAgentBench](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data) | Agentic multi-hop | v2: `comparison_structured` answer + structured claims | ≥2 accessions |

Quotas are **config-only** (`profile_quotas` in YAML); the shipped v1 config uses ~equal thirds.

---

## Issuer allowlist

Issuers are drawn from a **committed JSON allowlist** (`configs/benchmarks/issuer_allowlist_v1.json`), not from ad-hoc CLI flags. The allowlist is the union of tickers tagged by provenance:

| Source tag | Origin |
|------------|--------|
| `financebench` | Tickers commonly present in [FinanceBench](https://github.com/patronus-ai/financebench) open releases |
| `finder` | Tickers extracted from [FinDER](https://huggingface.co/datasets/Linq-AI-Research/FinDER) sample queries |
| `finagentbench` | [FinAgentBench](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data) / project fixture overlap |
| `benchmark_universe` | Sector-diverse expansion tickers (healthcare, energy, industrials, etc.) |
| `fixture` | Directories under `tests/fixtures/sec_downloads/` |

**v1 allowlist (20 tickers):** AAPL, AMZN, BAC, CAT, CVX, DIS, GOOGL, HD, JNJ, JPM, KO, META, MSFT, NVDA, PG, TSLA, UNH, V, WMT, XOM.

Rebuild after editing ticker lists in `scripts/build_issuer_allowlist.py` (updates `content_hash` required by the loader):

```bash
uv run python scripts/build_issuer_allowlist.py \
  --output configs/benchmarks/issuer_allowlist_v1.json
```

To use a custom pool, copy the JSON, add entries, rebuild hash via the script, and point `allowlist_path` in your generation config. Keep `issuer_sample_count` ≤ allowlist size ≤ `governance.max_issuers`.

Sampling is seed-random: with `random_seed: 42` and `issuer_sample_count: 20`, all 20 allowlist issuers are selected each run (shuffled, then take first *N*).

---

## CLI

Command group: `agent-query benchmark-dataset`

| Subcommand | Purpose |
|------------|---------|
| `generate` | Run sampling → materialize → judge (or single `--phase`) |
| `publish` | Promote draft to `data/benchmarks/custom-judge/v{version}/` |
| `reproduce` | Recompute and verify `items_hash` offline |
| `extend` | New draft from a published parent version + delta config |

### Live EDGAR smoke (default local test)

Requires `.env`: `SEC_EDGAR_USER_AGENT`, `GOOGLE_API_KEY`. Do **not** set `USE_FIXTURE_INGESTION`.

```bash
uv run agent-query benchmark-dataset generate \
  -c configs/benchmarks/custom_judge_live.yaml \
  --run-id live-edgar-smoke \
  --target-items 2 \
  --trace verbose
```

### Production-scale draft (v1 target ≥200 items)

```bash
uv run agent-query benchmark-dataset generate \
  -c configs/benchmarks/custom_judge_v1.yaml \
  --run-id pilot-20260530 \
  --trace verbose
```

Review `generation_report.json` before publish. **v1**: `pass_rate` ≥ 0.95 and `accepted_count` ≥ 200 are **blocking**. **v2**: see [Bundle v2.0](#bundle-v20-net-new-pool) — candidate `pass_rate` is indicative only; publish gates judge final `dev.jsonl`.

The judge phase generates **`governance.max_items`** candidates by default (220 for `custom_judge_v1.yaml`). Use `--target-items N` only to override for smoke runs (e.g. `--target-items 2`). Sampling and materialize are **not** re-run when you resume with `--phase judge`.

### Resume judge phase only (corpus already materialized)

If sampling/materialize finished but the judge phase stopped early (network error, Ctrl+C, etc.), **re-run the same command**. Progress is checkpointed in `{draft}/candidates.jsonl` after **each** item; the next run continues from item **N+1** automatically (same `--run-id`, `--phase judge`).

```bash
uv run agent-query benchmark-dataset generate \
  -c configs/benchmarks/custom_judge_v1.yaml \
  --run-id paper-v1-build \
  --phase judge \
  --trace verbose
```

Check progress:

```bash
wc -l data/benchmarks/custom-judge/drafts/paper-v1-build/candidates.jsonl
```

Gemini calls retry transient disconnects (`RemoteProtocolError`) up to 5 times with backoff before failing an item. Expect ~220 Gemini calls total and several hours wall-clock. To smoke-test item authoring without replacing a large draft, pass `--target-items 2` explicitly.

### Phased runs

```bash
uv run agent-query benchmark-dataset generate -c configs/benchmarks/custom_judge_live.yaml \
  --run-id live-edgar-smoke --phase sampling --trace verbose

uv run agent-query benchmark-dataset generate -c configs/benchmarks/custom_judge_live.yaml \
  --run-id live-edgar-smoke --phase materialize --trace verbose

uv run agent-query benchmark-dataset generate -c configs/benchmarks/custom_judge_live.yaml \
  --run-id live-edgar-smoke --phase judge --target-items 2 --trace verbose
```

Console tracing uses Rich panels on stderr (`--trace quiet|normal|verbose`), same spirit as `agent-query ask --trace`.

---

## Configuration reference

| File | Role |
|------|------|
| `configs/benchmarks/custom_judge_v1.yaml` | Production v1 defaults (**20 issuers**, ≥200 items, equal-thirds quotas) |
| `configs/benchmarks/custom_judge_v2.yaml` | Production **v2.0** net-new pool (seed 20260602, answer-GT-only, `multi_filing_min: 40`) |
| `configs/benchmarks/custom_judge_live.yaml` | Live EDGAR + Gemini smoke (1 issuer, 2 items) |
| `configs/benchmarks/custom_judge_ci.yaml` | CI mock path (`--mock-judge` only) |
| `configs/benchmarks/custom_judge_v1_extend.yaml` | Example extend delta config |
| `configs/benchmarks/issuer_allowlist_v1.json` | Committed 20-ticker union (FinanceBench / FinDER / FinAgentBench / benchmark_universe / fixtures) |
| `configs/benchmarks/inspiration_profiles/*.yaml` | Per-profile Gemini prompt templates (see [Design references](#design-references-papers-and-datasets)) |
| `configs/judges/gemini_2_5_pro.yaml` | Model pin (`gemini-2.5-pro`, temperature 0) |
| `scripts/build_issuer_allowlist.py` | Regenerates allowlist JSON + content hash |

**v1 governance defaults** (`custom_judge_v1.yaml`):

| Field | Value |
|-------|-------|
| `issuer_sample_count` / `max_issuers` | 20 |
| `max_filings_per_issuer` | 4 (latest 10-K + quarterly 10-Qs within fiscal year window) |
| `max_items` | 220 (headroom above 200 publish gate) |
| `max_judge_api_calls` | 800 |
| `validation_pass_rate` | 0.95 |
| `random_seed` | 42 |

Key YAML fields (see [generation-config-schema](../specs/011-judge-eval-dataset/contracts/generation-config-schema.md)):

- `random_seed`, `issuer_sample_count`, `allowlist_path`
- `filing_filters` — form types, fiscal year range, max filings per issuer
- `profile_quotas` — must sum to 1.0 ± 0.01
- `governance` — caps, `validation_pass_rate`, `dedup_similarity_threshold`, `judge_retries_per_item`
- `output.drafts_root` / `published_root`

Regenerate allowlist after ticker changes (see [Issuer allowlist](#issuer-allowlist)):

```bash
uv run python scripts/build_issuer_allowlist.py
```

---

## Draft bundle layout

After `generate`, artifacts live under:

```text
data/benchmarks/custom-judge/drafts/{run_id}/
├── manifest.json                 # DatasetManifest (status: draft)
├── generation_config.yaml        # Frozen config copy
├── sampling_manifest.json        # Issuers, accessions, config/allowlist hashes
├── generation_report.json        # Pass rate, rejections, judge API counts
├── corpus_bundle.json            # Snapshot ids, corpus paths, artifact hashes
├── candidates.jsonl              # All candidates (accepted + rejected; checkpoint order)
├── dev_selection_report.json     # v2: pool size, targets, selected profile counts
├── items/
│   ├── dev_pool.jsonl            # v2: all unique accepted items (may exceed 200)
│   └── dev.jsonl                 # Primary eval split (200 quota-balanced in v2)
└── corpus/
    ├── graph_node_index.json     # Valid section paths for FR-009
    └── graphs/{TICKER}/{snapshot_id}/…
```

Published versions mirror this under `data/benchmarks/custom-judge/v{version}/` with `status: published`. Large `corpus/**` trees are intended for **Git LFS** on publish.

---

## Evaluating generation quality

Use these files **in order** when reviewing a draft run (e.g. `drafts/live-edgar-smoke/`).

### 1. `generation_report.json` — run health

Check first:

- `accepted_count` / `candidates_total` and `pass_rate`
- `rejections_by_reason` — e.g. `unknown_section_path`, `missing_ground_truth`, `required_claims`, `finagentbench_requires_multi_filing`
- `judge_api_calls`, `duration_seconds`, `budget_exceeded`

**v2**: `pass_rate` measures candidate validation yield (duplicates count as non-blocking). It is **not** a publish gate. Tune generation using this metric; publish quality is judged on `items/dev.jsonl` only.

Low pass rate before tuning prompts: inspect rejection counts here, then drill into `candidates.jsonl`.

### 2. `dev_selection_report.json` — v2 profile balance (when present)

After judge phase or publish, confirms quota-balanced selection:

- `pool_count` — rows in `dev_pool.jsonl`
- `selected_count` — rows written to `dev.jsonl` (200 for production v2)
- `targets` / `selected_counts` — per-profile allocation (e.g. financebench 68, finder 66, finagentbench 66 for equal-thirds quotas)

### 3. `items/dev.jsonl` — accepted items (primary review)

One JSON object per line. For each item verify:

| Field | Accuracy check |
|-------|----------------|
| `question` | Clear, answerable from the bound filings, matches inspiration profile style |
| `ground_truth.answer` / `ground_truth.rubric` | Factually correct vs source filing. **v1 profile rules:** `financebench` requires `answer`; `finder` requires `rubric` (answer optional); `finagentbench` requires answer or rubric. **v2:** every item requires non-empty `answer`; `required_claims` for narrative/comparison types; rubric auxiliary only. |
| `answer_type` | **v2**: `numeric`, `short_label`, `narrative`, or `comparison_structured` |
| `expected_bindings.accessions` | Subset of accessions in `sampling_manifest.json` |
| `expected_bindings.fiscal_periods` | Align with filing period (FY/Q labels) |
| `expected_section_paths` | Point to real sections; cross-check `corpus/graph_node_index.json` |
| `inspiration_profile` | Matches intended quota mix |
| `validation_status` | Should be `accepted` in this file |

Quick inspect:

```bash
jq -r '.question' data/benchmarks/custom-judge/drafts/live-edgar-smoke/items/dev.jsonl
jq . data/benchmarks/custom-judge/drafts/live-edgar-smoke/items/dev.jsonl
```

### 4. `items/dev_pool.jsonl` — v2 full accept pool

All unique accepted items before quota selection. Use when you need extra finagentbench/financebench rows to backfill a draft without re-running Gemini on rejected candidates.

### 5. `candidates.jsonl` — rejected items and errors

Same schema as dev rows but includes `validation_status: rejected` and `validation_errors[]`. Use this to see **what Gemini produced before validation** and why items failed (hallucinated paths, wrong accession, empty rubric, duplicates).

### 6. `corpus/graph_node_index.json` — grounding audit

Lists every resolvable `{accession}/{section_slug}` exported from materialized graphs. Confirm each `expected_section_path` in dev items appears in `paths`. Paths missing here indicate materialize/index bugs, not just bad judge output.

```bash
jq -r '.expected_section_paths[]' data/benchmarks/custom-judge/drafts/live-edgar-smoke/items/dev.jsonl \
  | sort -u
jq -r '.paths[]' data/benchmarks/custom-judge/drafts/live-edgar-smoke/corpus/graph_node_index.json \
  | sort -u
```

### 7. `sampling_manifest.json` — filing binding context

Shows which tickers and accessions were frozen for this run. Verify items reference filings that were actually materialized (not adjacent filings from EDGAR that were filtered out).

### 8. `manifest.json` — draft summary

- `item_count`, `profile_counts`, `items_hash`
- `generation_judge_version` / `evaluation_judge_version` pins
- `corpus_bundle.snapshot_id` — needed for downstream eval

### 9. Source corpus (optional deep dive)

To manually verify answers:

- Raw packages: `data/raw/sec_downloads/{ticker}/{accession}/`
- Parsed JSON: `data/parsed/{ticker}/{accession}.json`
- Graph snapshot: draft `corpus/graphs/{TICKER}/{snapshot_id}/` or `data/graphs/{TICKER}/`

Open the HTML/XBRL sections referenced in `expected_section_paths` and compare to `ground_truth`.

### 10. Console trace (runtime)

Re-run with `--trace verbose` to see phase timings, per-item Gemini latency, and question previews on stderr. Useful when debugging retries without re-materializing.

---

## Publish and evaluate

When satisfied with the draft:

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/{run_id} \
  --version 1.0.0
```

**v1 publish gates** (unless `--skip-gates`): ≥200 items in `dev.jsonl` and `generation_report.pass_rate` ≥ 0.95.

**v2 publish** requires `--publish-signoff` and gates on final `dev.jsonl` quality (answer-GT coverage, feasibility, ≥40 multi-filing, macro-bindability, operator audit). Re-runs profile-balanced selection from `dev_pool.jsonl` when the pool exceeds 200 items. See [Bundle v2.0](#bundle-v20-net-new-pool).

Offline hash check:

```bash
uv run agent-query benchmark-dataset reproduce --version 1.0.0
```

Run agent against the bundle (see [011 quickstart](../specs/011-judge-eval-dataset/quickstart.md) for smoke eval with `custom-judge` registry).

---

## Environment variables

| Variable | Generate | Eval |
|----------|----------|------|
| `SEC_EDGAR_USER_AGENT` | Required (live EDGAR) | Not required when offline |
| `GOOGLE_API_KEY` | Required (live judge) | Eval judge if not mocking |
| `USE_FIXTURE_INGESTION=1` | CI fixtures only | — |
| `USE_MOCK_JUDGE=1` | CI + `custom_judge_ci` only | CI |
| `OFFLINE_BENCHMARK=1` | — | Blocks EDGAR during eval |
| `EDGAR_REQUESTS_PER_SECOND` | Optional (default 8); lower to 5 if you see transport disconnects during long generates |

**Judge phase and EDGAR:** `--phase judge` uses **Gemini + the frozen draft corpus only** (local `graph_node_index.json`). It does not download filings. EDGAR is used in **sampling** (catalog) and **materialize** only. If you saw EDGAR disconnects while resuming judge, an earlier CLI rebuilt the live accession catalog at the start of every `generate` call — that is fixed; use `--phase judge` after updating.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| `RemoteProtocolError: Server disconnected without sending a response` | Transient fault during **materialize** (EDGAR) or **judge** (Gemini). Automatic retries (5× backoff). Re-run `--phase judge` with the same `--run-id` to resume from `candidates.jsonl`. |
| Judge stopped mid-run (e.g. 112/220 items) | `wc -l …/candidates.jsonl` then re-run `--phase judge` — continues at item 113. |
| Rate limit / 429 | Reduce `EDGAR_REQUESTS_PER_SECOND`; wait and resume phased run (`--phase materialize` or `--phase judge`) |

---

## Architecture boundaries

Generation code under `src/evaluation/generation/` must **not** import retrieval or ingestion fetch paths. Materialization is orchestrated only from `src/cli/benchmark_materialize.py`. See [judge-generation-boundary](../specs/011-judge-eval-dataset/contracts/judge-generation-boundary.md).

---

## Next step: paper-v1.0 reproduction

After publish, run phase 2 on the frozen corpus:

- **[Research reproduction guide](research-reproduction.md)** — `repro run-all` on `releases/paper-v1.0/manifest.yaml`
- **Baseline checksums:** `releases/paper-v1.0/expected_checksums.json`
- **Local reference run:** `reports/repro-paper-v1.0/` (gitignored)

---

## Published bundle structure

The **v2.0.0** bundle is a greenfield dataset: seed `20260602`, fiscal window 2023–2026, **100% non-empty `ground_truth.answer`**, structured `required_claims`, and ≥40 multi-filing items. Path: `data/benchmarks/custom-judge/v2.0.0/`.

### Profile-balanced selection

`profile_quotas` in YAML (default ~34% / 33% / 33%) schedule **generation attempts** only. The final 200-item dev split is built by `profile_selection.py`:

1. **Judge phase** writes all unique accepts to `items/dev_pool.jsonl`.
2. `apply_profile_balanced_dev_split` selects 200 items using largest-remainder quotas (e.g. 68 / 66 / 66).
3. Selection is **deterministic** (`random_seed` + `item_id` hash).
4. **Publish** re-runs selection from `dev_pool.jsonl` before gates, writes `dev_selection_report.json`.

Console output highlights the balanced split:

```text
dev_selected=200 (profile-balanced from pool of 403)
dev_profile_counts=financebench=68, finder=66, finagentbench=66
```

### Generate and publish

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-YYYYMMDD \
  --bundle-version 2.0.0

# Resume judge only (revalidates candidates + rebuilds dev_pool/dev split):
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-YYYYMMDD \
  --bundle-version 2.0.0 \
  --phase judge

# After 20-item stratified audit (publish_audit.sample.json):
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/v2-draft-YYYYMMDD \
  --version 2.0.0 \
  --publish-signoff \
  --operator-id "${USER}"
```

### v2 publish gates (blocking)

| Gate | Rule |
|------|------|
| `item_count` | 200 rows in `dev.jsonl`; matches manifest |
| `answer_gt_coverage` | 1.0 |
| `rubric_only_count` | 0 |
| `multi_filing_count` | ≥ 40 |
| `macro_bindability_failures` | 0 |
| `blocked_count` | 0 |
| `publish_audit.json` | Present with operator sign-off |

**Not blocking**: `generation_report.pass_rate` (raw candidate yield).

Paper reproduction: [research-reproduction.md](research-reproduction.md) · `releases/paper-v1.0/manifest.yaml`

---

## Quality pass workflow (v2.0.1 / paper-v1.1)

Feature **018** adds a human-in-the-loop path to patch the frozen **200-item `dev.jsonl`** in place (no `dev_pool` re-selection). Published **v2.0.0** and **paper-v1.0** remain immutable; quality work targets a draft extended from v2.0.0 and publishes **v2.0.1** with a new **paper-v1.1** release lock.

**Operator guide:** [eval-dataset-quality.md](eval-dataset-quality.md) · [018 quickstart](../specs/018-eval-dataset-quality/quickstart.md) · **Checklist:** [quality-pass.md](../specs/018-eval-dataset-quality/checklists/quality-pass.md)

### Two paths: bulk generation fix vs CSV review

1. **Bulk fix boilerplate** (preferred for comparison co-occurrence answers): `review fix-boilerplate`
2. **CSV annotation** (exceptions): `review export-sheet` → edit CSV → `review import-csv --apply`

See [eval-dataset-quality.md](eval-dataset-quality.md) for the full tier-1 workflow.

### Quick commands

```bash
# 1. Extend v2.0.0 into a quality draft
uv run agent-query benchmark-dataset extend-quality \
  --parent-version 2.0.0 \
  --config configs/benchmarks/custom_judge_v2_quality.yaml \
  --run-id quality-v2.0.1

# 2. Export reproduction-driven review queue (tier-1 = high retrieval + zero outcome)
uv run agent-query benchmark-dataset review export-queue \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0 \
  --variant graph-full \
  --tier 1

# 2b. Bulk-fix boilerplate comparisons (generation-level; preferred over hand edits)
uv run agent-query benchmark-dataset review fix-boilerplate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --dry-run

# 2c. CSV annotation sheet for exceptions
uv run agent-query benchmark-dataset review export-sheet \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --repro-input reports/repro-paper-v1.0 \
  --output annotation_sheet_tier1.csv
# Fill CSV → import-csv --apply (see docs/eval-dataset-quality.md)

# 3. Annotate + apply approved overrides
uv run agent-query benchmark-dataset review annotate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finagentbench-0022 \
  --failure-class gt_boilerplate \
  --corpus-spot-check passed \
  --reviewer-id "${USER}"

uv run agent-query benchmark-dataset review apply-overrides \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1

# 4. Selective re-judge fixed items (same agent checkpoints, updated GT)
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variant graph-full \
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file fixed_items.json \
  --force-rescore

# 5. Publish v2.0.1 and adopt paper-v1.1
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --version 2.0.1 --publish-signoff
```

**v2.0.1 publish gates** add `boilerplate_comparison_count == 0` to the scorability report. Sidecar files (`annotations.jsonl`, `override_changelog.jsonl`) are copied to the published bundle for audit.

---

## Further reading

| Topic | Location |
|-------|----------|
| Feature requirements and success criteria | [spec.md](../specs/011-judge-eval-dataset/spec.md) |
| **v2.0 bundle contract, gates, CLI** | [017 quickstart](../specs/017-custom-judge-v2/quickstart.md) · [bundle-v2.0](../specs/017-custom-judge-v2/contracts/bundle-v2.0.md) · [generation-v2-cli](../specs/017-custom-judge-v2/contracts/generation-v2-cli.md) |
| Comparison-structured GT | [comparison-gt-template](../specs/017-custom-judge-v2/contracts/comparison-gt-template.md) |
| Paper table reproduction (phase 2) | [research-reproduction.md](research-reproduction.md) |
| Allowlist, materialization boundary, governance decisions | [research.md](../specs/011-judge-eval-dataset/research.md) |
| Generation config schema | [generation-config-schema](../specs/011-judge-eval-dataset/contracts/generation-config-schema.md) |
| Dataset bundle manifest | [dataset-bundle-manifest](../specs/011-judge-eval-dataset/contracts/dataset-bundle-manifest.md) |
| Trajectory judge evaluation (feature 010) | [010 quickstart](../specs/010-mlflow-trajectory-judge-eval/quickstart.md) |
