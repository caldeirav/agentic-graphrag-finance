# Implementation Plan: Research Reproduction Kit (Graph-Grounded Agentic Retrieval)

**Branch**: `012-research-repro-kit` | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-research-repro-kit/spec.md` with clarifications: custom-judge only headline tables; live re-execution with tolerance bands; five-variant ablation suite; dense flat-chunk baseline; all evidence chunk types for relevance labels; full published `dev` split.

## Summary

Deliver a **scripted research reproduction kit** for paper tag `paper-v1.0` that (1) verifies frozen custom-judge corpus via release manifest, (2) materializes graph-derived `relevant_chunk_ids`, (3) **live re-executes** five system variants offline on the full `dev` split, and (4) exports headline / by-profile / variant-delta / audit tables with checksum verification. Builds on evaluation registry + runner (001/010), graph snapshots (004), and published custom-judge bundles (011). Adds evaluation-layer flat-chunk baseline, declarative ablation flags in retrieval graph builder, and `agent-query repro` CLI.

## Technical Context

**Language/Version**: Python 3.12+ (`pyproject.toml`)

**Primary Dependencies**: Pydantic v2, existing `EvaluationRunner` / `CustomJudgeDataset`, `graph.store` + `GraphNodeType`, Typer CLI, MLflow, **sentence-transformers** (optional extra `reproduction`), LangGraph (graph-full + ablations only)

**Storage**:
- Release manifests: `releases/{tag}/manifest.yaml` + `expected_checksums.json`
- Variant configs: `configs/reproduction/variants/*.yaml`
- Embedding config: `configs/reproduction/embeddings/all_minilm_l6_v2.yaml`
- Repro outputs: `reports/repro-{tag}/`
- Extends 011 bundle with `relevance_labels.json`, optional `corpus/chunk_embeddings/`

**Testing**: pytest — unit (relevance traversal, flat-chunk ranking, export aggregates, tolerance verify); contract (release manifest, variant config, table schema); integration (repro smoke ≤20 items, offline EDGAR guard, reproduce structural metrics exact)

**Target Platform**: Local CLI batch (`agent-query repro`); CI smoke with mocks

**Project Type**: CLI + evaluation library extensions (`src/evaluation/reproduction/`)

**Performance Goals**: Full paper-v1.0 ≤8 h reference machine; CI smoke ≤15 min; relevance materialize ≤5 min on v1 bundle; embedding cache build once per bundle+model

**Constraints**:
- `OFFLINE_BENCHMARK=1` mandatory for repro runs (zero live EDGAR)
- Headline eval: **custom-judge only** — no upstream FinDER/FinanceBench/FinAgentBench adapters
- Flat-chunk baseline in **evaluation layer** — no LangGraph navigation
- Relevance materialization deterministic; ≥90% coverage gate
- Live re-execution: structural/ranking exact; judge metrics within manifest tolerance bands

**Scale/Scope**: ≥200 items × 5 variants; 3 inspiration_profile strata; paper tag + CI smoke tag

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Relevance labels from bundled graph only; repro fails closed on hash mismatch; no oracle retrieval | **PASS** — FR-006/008; verify-corpus gate |
| **II. Structural Semantics Preservation** | Reuses frozen 011 corpus from production Docling/XBRL materialization; chunk types preserve table/XBRL structure | **PASS** — no re-parse; bundle-only |
| **III. Traceability** | Each variant run logs MLflow parent/child runs, variant_id, trajectory artifacts | **PASS** — extends 010 patterns |
| **IV. Separation of Concerns** | Repro orchestration + flat-chunk + export in `evaluation/reproduction/`; ablations via declarative flags to retrieval graph; relevance does not import orchestration | **PASS** — see contracts |
| **V. Code Health & Environment Stability** | Pydantic models for ReleaseManifest, RelevanceLabelSet, exports; `uv` + optional locked extra | **PASS** — `data-model.md` |
| **VI. Rigorous Agent Evaluation** | Modular custom-judge eval; five variants; external judge; table exports with audit exclusions | **PASS** — FR-009–011 |

**Post-design re-check**: Phase 1 contracts preserve boundaries. **Minor retrieval change**: `build_agent_graph` accepts optional `VariantCapabilities` — documented in Complexity Tracking; no evaluation logic in retrieval.

## Project Structure

### Documentation (this feature)

```text
specs/012-research-repro-kit/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 entities
├── quickstart.md        # Operator / researcher guide
├── contracts/
│   ├── release-manifest.md
│   ├── system-variant-config.md
│   ├── relevance-materialize.md
│   ├── reproduction-cli.md
│   └── paper-table-export.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   └── reproduction.py              # NEW: ReleaseManifest, SystemVariant, RelevanceLabelSet, exports
├── evaluation/
│   ├── reproduction/                # NEW: repro kit (no generation imports)
│   │   ├── manifest.py              # load/validate release manifest
│   │   ├── corpus_verify.py         # LFS hash gate
│   │   ├── relevance.py             # materialize relevant_chunk_ids
│   │   ├── flat_chunk.py            # dense embedding baseline
│   │   ├── structural.py            # accession/section/multi-filing metrics
│   │   ├── runner.py                # multi-variant orchestration
│   │   ├── export.py                # paper table CSV/TeX
│   │   └── verify_tables.py         # tolerance checksum compare
│   ├── runner.py                    # EXTEND: variant_id param, structural metrics
│   └── datasets/custom_judge.py     # EXTEND: relevance manifest fields
├── retrieval/
│   └── orchestration/
│       ├── graph.py                 # EXTEND: variant_profile ablation edges
│       └── variant_profile.py       # NEW: VariantCapabilities model + helpers
├── cli/
│   └── commands/
│       └── repro.py                 # NEW: repro subcommand group

configs/reproduction/
├── variants/                        # five variant YAMLs
└── embeddings/all_minilm_l6_v2.yaml

releases/
├── paper-v1.0/
│   ├── manifest.yaml
│   └── expected_checksums.json
└── paper-smoke/                     # CI fixture manifest

tests/
├── unit/test_relevance_materialize.py
├── unit/test_flat_chunk_baseline.py
├── unit/test_paper_table_export.py
├── contract/test_release_manifest.py
├── contract/test_repro_import_boundary.py
└── integration/test_repro_smoke.py

docs/
└── benchmark-reproduction.md        # UPDATE: pointer to 012 quickstart
```

**Structure Decision**: Single Python project; new code primarily under `src/evaluation/reproduction/` with minimal retrieval hooks for ablation flags. Release artifacts under `releases/` committed at paper tag.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Retrieval graph accepts `VariantCapabilities` | Declarative ablations (FR-005) must disable macro/walker/HTML paths inside production agent | Separate forked graphs per variant — unmaintainable for paper + future sweeps |
| Optional `sentence-transformers` dep | Dense flat-chunk baseline (FR-004a) requires embedding model | BM25-only rejected in clarify; API embeddings add repro cost |
| Extend 011 manifest with relevance fields | Single source of truth for bundle integrity (FR-007) | Sidecar-only hash — breaks reproduce hash contract |

## Phase Overview

### Phase A — Scaffold & manifest (P1)

- Pydantic `ReleaseManifest`, loader, `releases/paper-smoke/` fixture
- `repro verify-corpus` with hash gate
- Contract tests for manifest schema

### Phase B — Relevance materialization (P1)

- `relevance.py` section→chunk traversal (four evidence types)
- CLI `materialize-relevance`; update 011 manifest fields
- Unit tests + coverage gate

### Phase C — Variant backends (P2)

- `FlatChunkBaseline` + embedding cache
- `VariantCapabilities` + graph ablation wiring
- Extend `EvaluationRunner` / new `ReproRunner` for variant_id + structural metrics

### Phase D — Multi-variant orchestration & export (P2)

- `repro run` / `run-all` offline orchestration
- `export.py` headline / by_profile / variant_delta / audit
- `verify-tables` with tolerance bands

### Phase E — Paper tag & docs (P3)

- `releases/paper-v1.0/manifest.yaml` (populated when v1 bundle published)
- Update `docs/benchmark-reproduction.md`, README repro section
- CI integration test `test_repro_smoke.py`

## Dependencies

| Feature | Usage |
|---------|-------|
| **001** | Benchmark registry, ranking metrics, `BenchmarkItem` |
| **004** | Graph snapshots, `CONTAINS` edges, chunk node types |
| **010** | Trajectory fidelity, incomplete exclusion, judge panel |
| **011** | Published custom-judge bundle, offline eval, manifest schema |

## Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| Full repro runtime >8 h | Document parallel variant runs (future); smoke path for CI |
| Embedding model drift | Pin HF revision in manifest; cache vectors in bundle |
| Relevance coverage <90% | Pre-publish materialize gate; failure report lists items |
| Ablation flags subtly change graph-full | Contract test: default profile ≡ current production graph |

## Generated Artifacts (this command)

| Artifact | Path |
|----------|------|
| Plan | `specs/012-research-repro-kit/plan.md` |
| Research | `specs/012-research-repro-kit/research.md` |
| Data model | `specs/012-research-repro-kit/data-model.md` |
| Quickstart | `specs/012-research-repro-kit/quickstart.md` |
| Contracts | `specs/012-research-repro-kit/contracts/*.md` |

**Next**: `/speckit-tasks` to generate dependency-ordered `tasks.md`.
