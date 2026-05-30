# Research: Judge-Generated Custom Evaluation Dataset (012)

**Feature**: 012-judge-eval-dataset | **Date**: 2026-05-20

## R1 — Issuer allowlist construction

**Decision**: Build `configs/benchmarks/issuer_allowlist_v1.json` as the **union of tickers** from FinanceBench open-source JSONL companies, FinDER HF sample queries (ticker extraction), FinAgentBench committed fixtures, and project fixtures (`AAPL`, etc.), deduplicated, with provenance tags per ticker.

**Rationale**: Spec clarification FR-001/FR-016 requires committed allowlist + seed-random subset; union aligns benchmark overlap without unbounded SEC crawl.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| S&P 500 full list | Too many EDGAR fetches; weak benchmark alignment |
| Manual 8-ticker list | Not reproducibly extensible for `extend` |
| Live EDGAR company search | Violates bounded sampling; non-reproducible |

**Implementation note**: One-time script `scripts/build_issuer_allowlist.py` (regeneratable); hash pinned in sampling manifest.

---

## R2 — Materialization orchestration boundary

**Decision**: **`src/cli/benchmark_materialize.py`** (CLI layer) accepts a sampling manifest and invokes **`cli.corpus_pipeline.run_materialize_pipeline`** per issuer; called only from `benchmark_dataset.py`. **`evaluation/generation/` MUST NOT** import `cli.corpus_pipeline` or `ingestion` fetch paths.

**Rationale**: Constitution IV and `contracts/judge-generation-boundary.md` — evaluation must not own parsing/graph logic; materialize stays in CLI facade; existing path preserves XBRL-first (Principle II).

**Alternatives considered**:
- `evaluation/generation/materialize_batch.py` calling corpus pipeline — **rejected** (violates layer boundary contract).
- Direct `graph.builder` calls from evaluation — duplicates pipeline gates and bypasses ingestion validators.
- Separate ad-hoc Docling invocation — violates production parity requirement (FR-002).

---

## R3 — Judge generation vs evaluation judge

**Decision**: **`JudgeGenerator`** class in `evaluation/generation/judge_generator.py` reuses **`GeminiJudgePanel` HTTP/client plumbing** with **separate prompt templates** under `configs/benchmarks/inspiration_profiles/`. Manifest records `generation_judge_version` and `evaluation_judge_version` independently; v1 default config sets both to `gemini-2.5-pro` / `configs/judges/gemini_2_5_pro.yaml`.

**Rationale**: Spec clarification allows divergent pins later; shared client reduces duplication.

**Alternatives considered**:
| Alternative | When to revisit |
|-------------|-----------------|
| Single shared prompt | Conflates item authoring with trajectory scoring |
| Non-Gemini generator (templates only) | Insufficient for novel question diversity at 200+ scale |

---

## R4 — Inspiration profile prompts (FinanceBench / FinDER / FinAgentBench)

**Decision**: Three YAML profiles map to structured JSON outputs:

| Profile | Question types | Required fields |
|---------|----------------|-----------------|
| `financebench` | metrics-generated, domain-relevant, novel-generated | `gold_answer`, single-filing `expected_section_paths` |
| `finder` | retrieval QA | `rubric`, `reference_evidence`, optional empty gold |
| `finagentbench` | agentic multi-hop | `multi_filing_required: true`, ≥2 accessions, cross-filing section paths |

**Rationale**: Mirrors published taxonomies ([FinanceBench README](https://github.com/patronus-ai/financebench), [FinDER HF card](https://huggingface.co/datasets/Linq-AI-Research/FinDER), ICAIF challenge) without copying upstream rows (spec assumption).

**Alternatives considered**: Single generic prompt — fails equal-thirds quota measurability (SC-001).

---

## R5 — Section path resolution

**Decision**: Expected section paths use **graph node id prefixes** `{accession}/{section_slug}` validated by lookup in bundled snapshot node index exported at materialize time (`corpus/graph_node_index.json`). Reject items when any path missing; retry judge up to **2** times per candidate (configurable).

**Rationale**: Aligns with existing graph-native navigation (009) and trajectory validator accession-prefix rules (010).

**Alternatives considered**:
- Free-text section titles only — not machine-verifiable (FR-009).
- Page numbers (FinanceBench PDF style) — mismatched with XBRL graph corpus; rubric may mention narrative but paths must be graph-native.

---

## R6 — Git LFS bundle layout

**Decision**: Track `data/benchmarks/custom-judge/**/corpus/**` via `.gitattributes` LFS filter. Manifest lists SHA-256 for each LFS object. `reproduce` verifies hashes after `git lfs pull`.

**Rationale**: Spec clarification; multi-issuer XBRL packages exceed plain Git limits.

**Alternatives considered**:
- External S3-only — adds infra; spec prefers LFS as canonical v1 path.
- Store only graph JSON (no raw XBRL) — breaks audit reproduction of ingestion chain.

---

## R7 — Governance defaults (v1 config)

**Decision**: Shipped defaults in `configs/benchmarks/custom_judge_v1.yaml`:

| Cap | Default |
|-----|---------|
| `max_issuers` | 12 |
| `max_filings_per_issuer` | 4 (latest 10-K + 3 quarterly) |
| `max_items` | 220 (headroom above 200 publish gate) |
| `max_judge_api_calls` | 600 |
| `max_storage_bytes` | 5_368_709_120 (5 GiB) |
| `max_wall_clock_seconds` | 14_400 (4 h) |
| `validation_pass_rate` | 0.95 |
| `dedup_similarity_threshold` | 0.85 |
| `profile_quotas` | financebench: 0.34, finder: 0.33, finagentbench: 0.33 |
| `random_seed` | 42 |

**Rationale**: Meets ≥200 items / ≥8 issuers with conservative EDGAR + Gemini budgets; overridable per spec FR-004/FR-007.

---

## R8 — Draft / publish / extend semantics

**Decision**:
- **Draft**: `data/benchmarks/custom-judge/drafts/{run_id}/` — writable, not registered.
- **Publish**: Promote to `data/benchmarks/custom-judge/v{semver}/`, compute manifest hash, register `custom-judge` adapter pointing at version.
- **Extend**: New semver with `parent_version`, merge parent items + delta; new snapshot id if issuers added.

**Rationale**: Spec clarification draft + explicit publish.

---

## R9 — Offline evaluation path

**Decision**: `CustomJudgeDataset` exposes `corpus_root` and `snapshot_id` from manifest; `EvaluationRunner` accepts optional `graph_root_override` to load bundled snapshot without EDGAR. Preflight sets `OFFLINE_BENCHMARK=1` to block ingestion network calls.

**Rationale**: SC-002 zero live EDGAR at eval time.

**Alternatives considered**: Copy bundle into `data/graphs/` on publish — mutates global state; override is cleaner.
