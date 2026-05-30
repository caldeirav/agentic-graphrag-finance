# Research: Research Reproduction Kit (012)

**Feature**: 012-research-repro-kit | **Date**: 2026-05-30

## R1 — Release manifest format and location

**Decision**: YAML manifest at `releases/{tag}/manifest.yaml` (e.g. `releases/paper-v1.0/manifest.yaml`), validated by Pydantic `ReleaseManifest`, with optional `expected_checksums.json` for aggregate table hashes.

**Rationale**: Human-readable pins (git SHA, judge/LLM/embedding versions) plus machine-verifiable hashes; tag `paper-v1.0` maps 1:1 to manifest path; CI smoke uses `releases/paper-smoke/manifest.yaml`.

**Alternatives considered**:
- Git tag annotations only — rejected: hard to diff and extend with tolerance bands.
- JSON-only — rejected: YAML better for multi-line pin blocks and comments.

---

## R2 — End-to-end reproduction entry point

**Decision**: Single Typer command group `agent-query repro` with subcommands `verify-corpus`, `materialize-relevance`, `run`, `export-tables`, and orchestrating wrapper `run-all` (calls verify → relevance gate → five variants → export).

**Rationale**: Matches spec FR-002 single entry; reuses existing `EvaluationRunner` patterns and 011 `benchmark-dataset reproduce` hash verification.

**Alternatives considered**:
- Shell script only — rejected: harder to test and enforce offline gates in CI.
- Extend `evaluation.cli` — rejected: paper repro spans dataset + variants + export; belongs in `cli/commands/repro.py`.

---

## R3 — Dense embedding model for flat-chunk baseline

**Decision**: Pin **`sentence-transformers/all-MiniLM-L6-v2`** (384-dim, CPU-viable) recorded in release manifest as `embedding_model_id` + config hash of `configs/reproduction/embeddings/all_minilm_l6_v2.yaml`.

**Rationale**: Aligns with 004 thematic-link research note; no API key; deterministic given model revision pin; strong enough baseline without oracle leakage.

**Alternatives considered**:
- BM25 — rejected in clarify (option B: dense only).
- OpenAI embeddings — rejected: adds API dependency and cost to reproduction.
- Hybrid RRF — rejected in clarify.

**Implementation note**: Add optional dependency group `reproduction = ["sentence-transformers>=3.0"]`; CI smoke uses precomputed embedding cache fixture to avoid model download.

---

## R4 — Flat-chunk baseline architecture (layer boundary)

**Decision**: Implement **`FlatChunkBaseline`** entirely under `src/evaluation/reproduction/flat_chunk.py`:
1. Load eligible chunk nodes from bundled graph snapshot(s) (same four evidence types as relevance labels).
2. Load or build content-addressed embedding cache under `{bundle}/corpus/chunk_embeddings/{model_id}/`.
3. Embed query, cosine top-k (default k=10, pinned in variant config).
4. Synthesize answer via same LLM + prompt contract as graph-full (via shared synthesis helper or mock in CI).

Ranking metrics use retrieved chunk ids; graph-structural metrics score binding/section expectations from item metadata (no graph navigation credit).

**Rationale**: Principle IV — baseline MUST NOT invoke LangGraph navigation; evaluation owns the comparison path; retrieval unchanged except ablation flags for graph-full variants.

**Alternatives considered**:
- Flag inside `QueryService` — rejected: couples retrieval to eval baseline logic.

---

## R5 — Ablation variant mechanism

**Decision**: Declarative **`SystemVariant`** YAML (`configs/reproduction/variants/*.yaml`) with capability flags passed into `QueryRequest.metadata["variant_profile"]` and read by `build_agent_graph(..., variant_profile=...)`:

| Variant id | Flags |
|------------|-------|
| `graph-full` | defaults (all stages on) |
| `flat-chunk` | handled by FlatChunkBaseline (not LangGraph) |
| `ablation-no-macro` | `disable_macro_router: true` — use pre-bound filings only, skip macro planning |
| `ablation-no-walker` | `disable_graph_walker: true` — section lookup without meso/micro hop traversal |
| `ablation-xbrl-only` | `xbrl_only: true` — exclude HTML-sourced narrative chunks from candidate sets |

**Rationale**: Spec FR-005 requires declarative config, not retrieval forks; minimal conditional edges in existing graph builder.

**Alternatives considered**:
- Separate graph compile per ablation — rejected: maintenance burden.
- Environment variables only — rejected: not manifest-auditable.

---

## R6 — Relevance label materialization

**Decision**: `materialize-relevance` step in `src/evaluation/reproduction/relevance.py`:
1. For each item, resolve `expected_section_paths` against bundled `graph_node_index.json`.
2. BFS/DFS from section node IDs following **`CONTAINS`** (and section hierarchy) outgoing edges.
3. Collect nodes where `node_type ∈ {CHUNK_PARAGRAPH, CHUNK_XBRL_FACT, CHUNK_TABLE, CHUNK_ROW}`.
4. Sort `relevant_chunk_ids` lexicographically by `node_id`.
5. Write updated JSONL + `relevance_labels.json` sidecar; update dataset manifest fields `relevance_labels_hash`, `relevance_coverage_rate`, `relevance_snapshot_id`.

Gate: ≥90% items non-empty; emit `relevance_report.json` listing failures.

**Rationale**: Clarify session A (all evidence types); deterministic; content-addressed hash for SC-002/SC-004.

**Alternatives considered**:
- Paragraph-only labels — rejected in clarify.
- Runtime derivation during eval — rejected: FR-007 requires persisted labels before eval.

---

## R7 — Paper table export schema

**Decision**: Export under `reports/repro-{tag}/{variant_id}/` with aggregator producing:

| File | Rows |
|------|------|
| `tables/headline.csv` | one row per variant × metric |
| `tables/by_profile.csv` | variant × inspiration_profile × metric |
| `tables/variant_delta.csv` | graph-full minus flat-chunk; each ablation minus graph-full |
| `tables/trajectory_audit.csv` | incomplete/degraded counts per variant |
| `tables/headline.tex` | optional LaTeX mirror |

Headline aggregates exclude `ValidationStatus.INCOMPLETE` and `judge_status=degraded` per FR-010.

**Rationale**: Spec FR-011; CSV for researchers, TeX optional for paper pipeline.

---

## R8 — Metric tolerance bands (judge-stochastic)

**Decision**: Release manifest documents absolute tolerances for live re-execution:

| Metric family | Tolerance |
|---------------|-----------|
| Outcome accuracy (mean) | ±0.02 |
| Rubric alignment (mean) | ±0.02 |
| Trajectory fidelity (mean) | ±0.02 |
| MRR, MAP, nDCG@10, structural rates | **exact** (±1e-9 float) |

`repro verify-tables` compares exported aggregates to manifest `expected_checksums.json`.

**Rationale**: Clarify Q1 (live re-execution with documented bands); structural/ranking deterministic on frozen labels.

---

## R9 — Reference machine and time bounds

**Decision**: Document reference profile in quickstart:

- **Hardware**: 8 vCPU, 32 GB RAM, no GPU required (MiniLM on CPU; LLM via LM Studio local or Gemini API per pins).
- **LFS**: ~2–4 GB pre-pulled custom-judge v1 corpus (20 issuers).
- **Wall clock**: ≤8 h for full `paper-v1.0` (≥200 items × 5 variants × ~30–45 s/item with live judge); CI smoke ≤15 min (≤20 items, mock judge/LLM, cached embeddings).

**Rationale**: SC-001 / FR-013; plan-phase quantification deferred from clarify.

---

## R10 — CI smoke reproduction path

**Decision**: Integration test `tests/integration/test_repro_smoke.py` using `tests/fixtures/repro/paper-smoke/` (≤20 items subset), `USE_MOCK_JUDGE=1`, `USE_MOCK_LLM=1`, runs `repro run-all --manifest releases/paper-smoke/manifest.yaml` in ≤15 min.

**Rationale**: FR-014 / SC-007; validates wiring without full paper cost.
