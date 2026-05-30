# Implementation Plan: Judge-Generated Custom Evaluation Dataset

**Branch**: `011-judge-eval-dataset` | **Date**: 2026-05-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-judge-eval-dataset/spec.md` with clarifications on allowlist sampling, draft+publish workflow, config-only profile quotas (v1 equal thirds), Git LFS corpus bundles, and separate judge pins (v1 same Gemini).

## Summary

Build an **offline dataset generation pipeline** that (1) seed-samples issuers from a committed allowlist, (2) materializes filings via the **production Docling/XBRL + graph path** (`cli.corpus_pipeline`), (3) uses **Gemini** (generation profile) to produce ≥200 grounded benchmark items with expected filing sets and section paths styled after FinanceBench / FinDER / FinAgentBench taxonomies, (4) validates and bundles artifacts for **zero-EDGAR evaluation**, and (5) registers **`custom-judge`** as a plug-in dataset. Operator workflow: `generate` → review draft → `publish`; `reproduce` / `extend` for versioning.

## Technical Context

**Language/Version**: Python 3.12+ (`pyproject.toml`)

**Primary Dependencies**: Pydantic v2, existing `cli.corpus_pipeline.run_materialize_pipeline`, `graph.store`, `evaluation/judges/gemini_panel.py` (generation prompts separate from eval rubric), Typer CLI, Git LFS (corpus binaries), MLflow (eval runs only)

**Storage**:
- Published bundles: `data/benchmarks/custom-judge/{version}/` (manifest, items, configs, reports)
- Corpus LFS: `data/benchmarks/custom-judge/{version}/corpus/` (raw + parsed + graph snapshot export)
- Allowlist: `configs/benchmarks/issuer_allowlist_v1.json`
- Drafts: `data/benchmarks/custom-judge/drafts/{run_id}/`

**Testing**: pytest — unit (sampler, validator, bundle hasher); contract (manifest schema, registry adapter, import boundary); integration (offline eval smoke ≥20 items, reproduce hash)

**Target Platform**: Local CLI batch jobs (`agent-query benchmark-dataset …`); CI uses `USE_MOCK_JUDGE=1` + fixture bundle subset

**Project Type**: CLI + library (`src/evaluation/generation/`, `src/cli/commands/benchmark_dataset.py`)

**Performance Goals**: Generation is batch/offline; checkpoint resume within 30s of interrupt; reproduce manifest hash in &lt;5 min on bundled corpus

**Constraints**:
- Evaluation generation modules MUST NOT import `retrieval.orchestration`, `retrieval.service`, or graph navigation policies
- Materialization MUST invoke `run_materialize_pipeline` / existing ingestion path (Principle II XBRL-first)
- v1 default: same Gemini pin (`configs/judges/gemini_2_5_pro.yaml`) for generation and evaluation
- Governance defaults in `configs/benchmarks/custom_judge_v1.yaml` (see research.md)
- Git LFS required for published corpus; manifest stores SHA-256 per artifact

**Scale/Scope**: v1 ≥200 items, ≥8 issuers, equal-thirds inspiration quotas; smoke eval ≥20 items

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Items validated against materialized graph; judge outputs rejected if section paths unresolved | **PASS** — FR-009 validator + fail-closed publish threshold |
| **II. Structural Semantics Preservation** | Reuses production Docling/XBRL materialization | **PASS** — `run_materialize_pipeline`, no ad-hoc flattening |
| **III. Traceability** | Eval runs log dataset version, seeds, judge pins (FR-015) | **PASS** — extends `EvaluationRun` metadata |
| **IV. Separation of Concerns** | Generation in `evaluation/generation/` + CLI orchestration; materialize via `cli/` facade; no retrieval imports in generation/judge modules | **PASS** — `contracts/judge-generation-boundary.md` |
| **V. Code Health & Environment Stability** | Pydantic models for all manifests; `uv` lockfile | **PASS** — `data-model.md` |
| **VI. Rigorous Agent Evaluation** | New modular dataset + registry plug-in; external judge for gen + eval | **PASS** — `CustomJudgeDataset` adapter |

**Post-design re-check**: Phase 1 contracts preserve layer boundaries. **No constitution exceptions required** — generation is offline-only, not on production `ask` hot path.

## Project Structure

### Documentation (this feature)

```text
specs/012-judge-eval-dataset/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dataset-generation-cli.md
│   ├── generation-config-schema.md
│   ├── dataset-bundle-manifest.md
│   ├── custom-judge-dataset-adapter.md
│   └── judge-generation-boundary.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   └── benchmark_generation.py    # NEW: GenerationConfig, manifests, GeneratedItem draft types
├── evaluation/
│   ├── generation/                # NEW: offline generation (no retrieval imports)
│   │   ├── sampler.py             # allowlist + seed issuer/filing selection
│   │   ├── materialize_batch.py   # multi-issuer wrapper → cli.corpus_pipeline
│   │   ├── judge_generator.py     # profile-specific Gemini prompts
│   │   ├── item_validator.py      # section path + filing resolution
│   │   ├── deduplicator.py
│   │   ├── bundle.py              # draft assembly, hash, publish promotion
│   │   └── governance.py          # budget counters, fail-stop
│   ├── datasets/
│   │   └── custom_judge.py        # NEW: BenchmarkDataset reading published bundle
│   └── registry.py                # register "custom-judge"
├── cli/
│   └── commands/
│       └── benchmark_dataset.py     # generate | publish | reproduce | extend

configs/benchmarks/
├── custom_judge_v1.yaml             # default generation config (equal thirds)
├── issuer_allowlist_v1.json
└── inspiration_profiles/
    ├── financebench.yaml
    ├── finder.yaml
    └── finagentbench.yaml

data/benchmarks/custom-judge/        # git + LFS (see .gitattributes)
├── drafts/{run_id}/
└── v1.0.0/
    ├── manifest.json
    ├── generation_config.yaml
    ├── sampling_manifest.json
    ├── generation_report.json
    ├── items/dev.jsonl
    └── corpus/                      # LFS: snapshots, raw SEC packages

tests/
├── unit/test_generation_sampler.py
├── unit/test_item_validator.py
├── contract/test_custom_judge_manifest.py
├── contract/test_generation_import_boundary.py
└── integration/test_custom_judge_offline_eval.py
```

**Structure Decision**: Generation logic lives under `evaluation/generation/`; **orchestration that touches ingestion/graph** goes through **`cli.corpus_pipeline`** from the Typer command layer to avoid evaluation→retrieval coupling. Published data under `data/benchmarks/custom-judge/`.

## Complexity Tracking

> No constitution violations requiring justification.

| Decision | Why | Simpler Alternative Rejected Because |
|----------|-----|--------------------------------------|
| Separate `evaluation/generation/` package | Keeps dataset construction out of adapters and retrieval | Inline scripts in `scripts/` — not testable, not registry-integrated |
| Git LFS for corpus | Spec clarification; multi-issuer XBRL bundles exceed Git limits | Git-only — fails SC-002 reproducibility at scale |
| Draft vs published paths | Spec clarification; operator review gate | Auto-publish — violates FR-014 |

## Gap Analysis (current code → target)

| Area | Current | Target (012) |
|------|---------|--------------|
| Custom dataset | None; synthetic fallback in `_base.load_jsonl_dataset` | `CustomJudgeDataset` + real bundled items |
| Generation pipeline | None | Full sampler → materialize → judge → validate → bundle |
| Issuer allowlist | Ad hoc fixtures | Versioned `issuer_allowlist_v1.json` |
| Benchmark CLI | `evaluation/cli.py` run-only | `agent-query benchmark-dataset` generate/publish/reproduce/extend |
| Item schema | `BenchmarkItem` without `expected_section_paths` | Extend model + JSONL row mapping |
| Offline eval | Requires live materialized graphs in `data/graphs/` | Bundle snapshot path override in eval runner config |

## Phase 0 / Phase 1 Deliverables

| Artifact | Status |
|----------|--------|
| [research.md](./research.md) | Complete |
| [data-model.md](./data-model.md) | Complete |
| [quickstart.md](./quickstart.md) | Complete |
| [contracts/](./contracts/) | Complete |

## Implementation Phases (for tasks.md)

**Phase A — Scaffold & config**: Models, allowlist builder script, default YAML, LFS `.gitattributes`, governance module.

**Phase B — Sampling & materialize**: Sampler tests; batch materialize via `run_materialize_pipeline`; sampling manifest hash.

**Phase C — Judge generation**: Three inspiration profile prompts; checkpointed Gemini calls; item validator + dedup.

**Phase D — Bundle & CLI**: Draft/publish/reproduce/extend commands; manifest hashing; generation report.

**Phase E — Registry & offline eval**: `CustomJudgeDataset`; runner snapshot path from bundle; integration smoke ≥20 items; reproduce hash test.

**Phase F — v1 dataset publish**: Run full generation (operator), publish `v1.0.0` with ≥200 items; document in quickstart.
