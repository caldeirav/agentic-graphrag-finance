# Custom-Judge Evaluation Dataset Generation

This guide describes how the project builds a **versioned, offline evaluation benchmark** from live SEC EDGAR filings. The pipeline samples issuers, materializes XBRL/graph snapshots through the same production path as `agent-query ask`, uses **Gemini** to author grounded Q&A items, validates them against the bundled graph index, and writes a reproducible draft bundle.

**Related specs:** [011 spec](../specs/011-judge-eval-dataset/spec.md) · [011 plan](../specs/011-judge-eval-dataset/plan.md) · [operator quickstart](../specs/011-judge-eval-dataset/quickstart.md)

---

## Goals

| Goal | How |
|------|-----|
| Grounded items | Every item binds to real accessions and resolvable `expected_section_paths` from the materialized graph |
| Reproducible sampling | Committed allowlist + `random_seed` → deterministic `sampling_manifest.json` hash |
| Production-faithful corpus | Materialization calls `cli.corpus_pipeline.run_materialize_pipeline` (Docling/XBRL + docling-graph) |
| Style diversity | Three **inspiration profiles** (FinanceBench / FinDER / FinAgentBench taxonomies) with configurable quotas |
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
  E --> E1[items/dev.jsonl]
  F --> F1[manifest.json + generation_report.json]
```

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
2. For each candidate, call **Gemini** (`GeminiItemGenerator`) with profile-specific prompts from `configs/benchmarks/inspiration_profiles/`.
3. **Validate** each item: non-empty question, ground truth or rubric, accessions ⊆ snapshot, every section path ∈ graph index; profile-specific rules (e.g. FinAgentBench ≥2 filings).
4. **Deduplicate** near-duplicate questions (similarity threshold from governance config).
5. Write accepted rows to `items/dev.jsonl`, all candidates to `candidates.jsonl`, finalize `manifest.json` (`status: draft`).

**Modules:** `src/evaluation/generation/judge_generator.py`, `gemini_item_generator.py`, `item_validator.py`, `deduplicator.py`, `bundle.py`

Mock mode (`USE_MOCK_JUDGE=1` + `custom_judge_ci` config) skips Gemini for CI.

---

## Inspiration profiles

Prompt templates live under `configs/benchmarks/inspiration_profiles/`:

| Profile | Style | Typical ground truth | Filing count |
|---------|-------|---------------------|--------------|
| `financebench` | Metrics, domain, novel generated | `ground_truth.answer` | Single-filing |
| `finder` | Retrieval QA | `ground_truth.rubric` | Single-filing |
| `finagentbench` | Agentic multi-hop | answer and/or rubric | ≥2 accessions |

Quotas are **config-only** (`profile_quotas` in YAML); the shipped v1 config uses ~equal thirds.

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

Review `generation_report.json` (`pass_rate` ≥ 0.95, `accepted_count` ≥ 200) before publish.

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
| `configs/benchmarks/custom_judge_v1.yaml` | Production v1 defaults (12 issuers, ≥200 items, equal-thirds quotas) |
| `configs/benchmarks/custom_judge_live.yaml` | Live EDGAR + Gemini smoke (1 issuer, 2 items) |
| `configs/benchmarks/custom_judge_ci.yaml` | CI mock path (`--mock-judge` only) |
| `configs/benchmarks/custom_judge_v1_extend.yaml` | Example extend delta config |
| `configs/benchmarks/issuer_allowlist_v1.json` | Committed issuer union (FinanceBench / FinDER / fixture tickers) |
| `configs/benchmarks/inspiration_profiles/*.yaml` | Per-profile Gemini prompt templates |
| `configs/judges/gemini_2_5_pro.yaml` | Model pin (`gemini-2.5-pro`, temperature 0) |

Key YAML fields (see [generation-config-schema](../specs/011-judge-eval-dataset/contracts/generation-config-schema.md)):

- `random_seed`, `issuer_sample_count`, `allowlist_path`
- `filing_filters` — form types, fiscal year range, max filings per issuer
- `profile_quotas` — must sum to 1.0 ± 0.01
- `governance` — caps, `validation_pass_rate`, `dedup_similarity_threshold`, `judge_retries_per_item`
- `output.drafts_root` / `published_root`

Regenerate allowlist after ticker changes:

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
├── candidates.jsonl              # All candidates (accepted + rejected)
├── items/
│   └── dev.jsonl                 # Accepted items only (primary eval split)
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
- `rejections_by_reason` — e.g. `unknown_section_path`, `missing_ground_truth`, `finagentbench_requires_multi_filing`
- `judge_api_calls`, `duration_seconds`, `budget_exceeded`

Low pass rate before tuning prompts: inspect rejection counts here, then drill into `candidates.jsonl`.

### 2. `items/dev.jsonl` — accepted items (primary review)

One JSON object per line. For each item verify:

| Field | Accuracy check |
|-------|----------------|
| `question` | Clear, answerable from the bound filings, matches inspiration profile style |
| `ground_truth.answer` / `ground_truth.rubric` | Factually correct vs source filing. **Profile rules:** `financebench` requires `answer`; `finder` requires `rubric` and may have `answer: null` (FinDER-style rubric-only scoring); `finagentbench` requires at least one of answer or rubric. |
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

### 3. `candidates.jsonl` — rejected items and errors

Same schema as dev rows but includes `validation_status: rejected` and `validation_errors[]`. Use this to see **what Gemini produced before validation** and why items failed (hallucinated paths, wrong accession, empty rubric, duplicates).

### 4. `corpus/graph_node_index.json` — grounding audit

Lists every resolvable `{accession}/{section_slug}` exported from materialized graphs. Confirm each `expected_section_path` in dev items appears in `paths`. Paths missing here indicate materialize/index bugs, not just bad judge output.

```bash
jq -r '.expected_section_paths[]' data/benchmarks/custom-judge/drafts/live-edgar-smoke/items/dev.jsonl \
  | sort -u
jq -r '.paths[]' data/benchmarks/custom-judge/drafts/live-edgar-smoke/corpus/graph_node_index.json \
  | sort -u
```

### 5. `sampling_manifest.json` — filing binding context

Shows which tickers and accessions were frozen for this run. Verify items reference filings that were actually materialized (not adjacent filings from EDGAR that were filtered out).

### 6. `manifest.json` — draft summary

- `item_count`, `profile_counts`, `items_hash`
- `generation_judge_version` / `evaluation_judge_version` pins
- `corpus_bundle.snapshot_id` — needed for downstream eval

### 7. Source corpus (optional deep dive)

To manually verify answers:

- Raw packages: `data/raw/sec_downloads/{ticker}/{accession}/`
- Parsed JSON: `data/parsed/{ticker}/{accession}.json`
- Graph snapshot: draft `corpus/graphs/{TICKER}/{snapshot_id}/` or `data/graphs/{TICKER}/`

Open the HTML/XBRL sections referenced in `expected_section_paths` and compare to `ground_truth`.

### 8. Console trace (runtime)

Re-run with `--trace verbose` to see phase timings, per-item Gemini latency, and question previews on stderr. Useful when debugging retries without re-materializing.

---

## Publish and evaluate

When satisfied with the draft:

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/{run_id} \
  --version 1.0.0
```

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

---

## Architecture boundaries

Generation code under `src/evaluation/generation/` must **not** import retrieval or ingestion fetch paths. Materialization is orchestrated only from `src/cli/benchmark_materialize.py`. See [judge-generation-boundary](../specs/011-judge-eval-dataset/contracts/judge-generation-boundary.md).
