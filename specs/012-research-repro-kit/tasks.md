---
description: "Task list for research reproduction kit (012)"
---

# Tasks: Research Reproduction Kit (Graph-Grounded Agentic Retrieval)

**Input**: Design documents from `specs/012-research-repro-kit/`

**Prerequisites**: plan.md, spec.md (with clarifications), research.md, data-model.md, contracts/, quickstart.md; features **001** (registry/metrics), **004** (graph), **010** (trajectory/judge), **011** (custom-judge bundle) on branch `012-research-repro-kit`

**Tests**: Contract, unit, and integration tests per plan testing strategy and spec success criteria (SC-001–SC-007, FR-014).

**Organization**: Foundational models and corpus verify block offline repro; **US2 relevance → US3 variants → US4 export → US1 run-all** form the eval pipeline; **US5** validates frozen corpus independently; polish adds CI smoke and docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/evaluation/reproduction/`, `src/models/reproduction.py`, `src/retrieval/orchestration/variant_profile.py`, `src/cli/commands/repro.py`, `configs/reproduction/`, `releases/`
- Extend: `src/evaluation/runner.py`, `src/evaluation/datasets/custom_judge.py`, `src/retrieval/orchestration/graph.py`, `src/cli/main.py`, `pyproject.toml`, `docs/benchmark-reproduction.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package scaffold, variant configs, smoke release manifest, CLI stub

- [X] T001 Create `src/evaluation/reproduction/__init__.py` exporting public repro API per `plan.md`
- [X] T002 Add optional dependency group `reproduction = ["sentence-transformers>=3.0"]` in `pyproject.toml` and run `uv lock`; commit updated `uv.lock` per `research.md` R3
- [X] T003 [P] Add five variant YAMLs under `configs/reproduction/variants/` per `contracts/system-variant-config.md`
- [X] T004 [P] Add `configs/reproduction/embeddings/all_minilm_l6_v2.yaml` (top_k, batch_size, cache policy) per `research.md` R3
- [X] T005 [P] Add smoke release `releases/paper-smoke/manifest.yaml` (all **five** variant ids, `--max-items` cap only) and `releases/paper-smoke/expected_checksums.json` per `contracts/release-manifest.md`
- [X] T006 [P] Add `releases/paper-v1.0/manifest.yaml` template with placeholder pins (git_sha, hashes TBD at publish) and full five-variant list per `plan.md` Phase E
- [X] T007 [P] Create `tests/fixtures/repro/paper-smoke/` with subset manifest pointers to `tests/fixtures/custom_judge/` corpus; fixture manifest MUST list same five variants as `paper-v1.0` per `quickstart.md` CI smoke
- [X] T008 Register Typer command group `repro` in `src/cli/main.py` pointing to `src/cli/commands/repro.py` with subcommand stubs per `contracts/reproduction-cli.md`

**Checkpoint**: `uv run agent-query repro --help` lists `verify-corpus`, `materialize-relevance`, `run`, `export-tables`, `verify-tables`, `run-all`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed manifest models, corpus hash gate, import boundary — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [X] T009 [P] Add `ReleaseManifest`, `ModelPins` (incl. `embedding_model_revision`, `embedding_config_hash`), `ToleranceBands`, `SystemVariant`, `VariantCapabilities`, `RelevanceLabelSet`, `ReproRun`, `PaperTableExport` in `src/models/reproduction.py` per `data-model.md`
- [X] T010 Implement `src/evaluation/reproduction/manifest.py` load/validate YAML release manifest including `embedding_model_revision` and config hashes per `contracts/release-manifest.md`
- [X] T011 [P] Add contract test `tests/contract/test_release_manifest.py` validating smoke fixture against Pydantic models
- [X] T012 [P] Add contract test `tests/contract/test_repro_import_boundary.py` forbidding `retrieval.orchestration` imports in `src/evaluation/reproduction/relevance.py` and `flat_chunk.py` per plan Complexity Tracking
- [X] T013 Implement `src/evaluation/reproduction/corpus_verify.py` hash-checking `corpus_hashes` against custom-judge bundle per `contracts/release-manifest.md`
- [X] T014 Wire `repro verify-corpus` in `src/cli/commands/repro.py` requiring `OFFLINE_BENCHMARK=1` per FR-002
- [X] T015 [P] Add unit test `tests/unit/test_corpus_verify.py` for pass/fail hash mismatch messages
- [X] T016 [P] Extend `DatasetManifest` / custom-judge manifest reader with optional `relevance_labels_hash`, `relevance_coverage_rate`, `relevance_snapshot_id` fields in `src/models/benchmark_generation.py` per `data-model.md`
- [X] T017 [P] Extend `src/evaluation/datasets/custom_judge.py` to expose new manifest relevance fields on `manifest()`

**Checkpoint**: `uv run pytest tests/contract/test_release_manifest.py tests/unit/test_corpus_verify.py -q` passes; `repro verify-corpus --manifest releases/paper-smoke/manifest.yaml` runs on fixture

---

## Phase 3: User Story 2 - Graph-Grounded Relevance Labels (Priority: P1)

**Goal**: Derive deterministic `relevant_chunk_ids` for ≥90% of items from bundled graph under `expected_section_paths`

**Independent Test**: Run `materialize-relevance` on fixture bundle; re-run yields identical `labels_hash`; coverage ≥90% or gate fails with report

### Tests for User Story 2

- [X] T018 [P] [US2] Add unit tests `tests/unit/test_relevance_materialize.py` for section traversal, four chunk types, deterministic ordering per `contracts/relevance-materialize.md`

### Implementation for User Story 2

- [X] T019 [US2] Implement `src/evaluation/reproduction/relevance.py` with CONTAINS traversal and evidence chunk collection per FR-006
- [X] T020 [US2] Write `relevance_labels.json` sidecar and canonical `labels_hash` in `src/evaluation/reproduction/relevance.py` per `contracts/relevance-materialize.md`
- [X] T021 [US2] Update `items/dev.jsonl` rows with `relevant_chunk_ids` and emit `relevance_report.json` on failures in `src/evaluation/reproduction/relevance.py`
- [X] T022 [US2] Enforce ≥90% coverage gate (exit 1 below threshold) in `src/evaluation/reproduction/relevance.py` per FR-008
- [X] T023 [US2] Wire `repro materialize-relevance` in `src/cli/commands/repro.py` updating 011 bundle `manifest.json` relevance fields per FR-007

**Checkpoint**: US2 unit tests pass; materialize on fixture yields stable hash; gate rejects mock bundle with &lt;90% coverage

---

## Phase 4: User Story 3 - Paired System Variant Evaluation (Priority: P2)

**Goal**: Run graph-full, flat-chunk, and three ablations on identical custom-judge items offline with per-item metrics

**Independent Test**: `repro run --variants graph-full,flat-chunk,ablation-no-macro,ablation-no-walker,ablation-xbrl-only --max-items 20` on smoke fixture; shared item ids; flat-chunk uses dense retrieval only

### Tests for User Story 3

- [X] T024 [P] [US3] Add unit tests `tests/unit/test_flat_chunk_baseline.py` for cosine top-k ranking and cache idempotence in `src/evaluation/reproduction/flat_chunk.py`
- [X] T025 [P] [US3] Add unit tests `tests/unit/test_variant_profile.py` for ablation flag parsing in `src/retrieval/orchestration/variant_profile.py`
- [X] T026 [P] [US3] Add unit tests `tests/unit/test_structural_metrics.py` for accession binding, section path hit, multi-filing success in `src/evaluation/reproduction/structural.py`

### Implementation for User Story 3

- [X] T027 [P] [US3] Add `VariantCapabilities` loader and helpers in `src/retrieval/orchestration/variant_profile.py` per `contracts/system-variant-config.md`
- [X] T028 [US3] Extend `build_agent_graph` in `src/retrieval/orchestration/graph.py` to honor `disable_macro_router`, `disable_graph_walker`, `xbrl_only` flags per `research.md` R5
- [X] T055 [P] [US3] Add contract test `tests/contract/test_variant_default_parity.py` asserting default `VariantCapabilities` (all flags false) yields same compiled stage set as pre-012 production graph per `plan.md` Risk & Mitigation
- [X] T056 [P] [US3] Add unit test `tests/unit/test_xbrl_only_ablation.py` verifying `xbrl_only` excludes HTML-sourced narrative chunks from candidate sets in `src/retrieval/orchestration/graph.py`
- [X] T029 [US3] Implement `FlatChunkBaseline` in `src/evaluation/reproduction/flat_chunk.py` with embedding cache under bundle `corpus/chunk_embeddings/` per FR-004a
- [X] T030 [US3] Implement `src/evaluation/reproduction/structural.py` computing graph-structural scores from trajectories per FR-009
- [X] T031 [US3] Implement `src/evaluation/reproduction/runner.py` orchestrating per-variant eval (langgraph vs flat_chunk backends) extending `EvaluationRunner` patterns per `plan.md`; flat-chunk path MUST call shared LLM synthesis + judge scoring for outcome/rubric metrics (FR-009)
- [X] T032 [US3] Pass `variant_profile` via `QueryRequest.metadata` from repro runner in `src/evaluation/reproduction/runner.py`
- [X] T033 [US3] Wire `repro run` subcommand in `src/cli/commands/repro.py` with `--variants`, `--max-items`, custom-judge only (FR-003)
- [X] T034 [US3] Exclude incomplete/degraded items from per-run aggregates in `src/evaluation/reproduction/runner.py` per FR-010

**Checkpoint**: Smoke run produces per-variant reports under `reports/repro-paper-smoke/{variant_id}/`; flat-chunk never invokes LangGraph

---

## Phase 5: User Story 4 - Stratified Reporting by Inspiration Profile (Priority: P2)

**Goal**: Export headline, by-profile, variant-delta, and trajectory audit tables in CSV (+ optional TeX)

**Independent Test**: Export from smoke run outputs `by_profile.csv` with rows per `inspiration_profile` × variant; finder stratum handles rubric-only N/A

### Tests for User Story 4

- [X] T035 [P] [US4] Add unit tests `tests/unit/test_paper_table_export.py` for aggregation rules and incomplete exclusion in `src/evaluation/reproduction/export.py`
- [X] T036 [P] [US4] Add contract test `tests/contract/test_paper_table_schema.py` validating CSV columns per `contracts/paper-table-export.md`

### Implementation for User Story 4

- [X] T037 [US4] Implement `src/evaluation/reproduction/export.py` producing `headline.csv`, `by_profile.csv`, `variant_delta.csv`, `trajectory_audit.csv` per FR-011
- [X] T038 [US4] Add optional `headline.tex` export in `src/evaluation/reproduction/export.py`
- [X] T039 [US4] Implement `src/evaluation/reproduction/verify_tables.py` comparing exports to manifest tolerances (exact structural/ranking) per `research.md` R8
- [X] T040 [US4] Wire `repro export-tables` and `repro verify-tables` in `src/cli/commands/repro.py`

**Checkpoint**: Export + verify-tables pass on committed smoke expected checksums fixture

---

## Phase 6: User Story 1 - Reproduce Paper Tables from a Tagged Release (Priority: P1) 🎯 MVP

**Goal**: Single `run-all` workflow rebuild-verifies corpus, gates relevance, runs five variants on full dev split, exports and verifies tables

**Independent Test**: `repro run-all --manifest releases/paper-smoke/manifest.yaml` completes offline; output dir contains all table files; structural metrics checksum exact

### Tests for User Story 1

- [X] T041 [P] [US1] Add integration test `tests/integration/test_repro_smoke.py` running full smoke workflow (all **five** manifest variants, ≤20 items) with `USE_MOCK_JUDGE=1` `USE_MOCK_LLM=1` in ≤15 min per SC-007 / FR-005a
- [X] T042 [P] [US1] Add integration test `tests/integration/test_repro_offline_guard.py` asserting zero EDGAR network calls when `OFFLINE_BENCHMARK=1` per SC-005

### Implementation for User Story 1

- [X] T043 [US1] Implement `run_all` orchestration in `src/evaluation/reproduction/runner.py`: verify-corpus → relevance gate → five variants → export; persist `repro_run.json` audit artifact per `contracts/reproduction-cli.md` and `data-model.md` ReproRun
- [X] T044 [US1] Wire `repro run-all` in `src/cli/commands/repro.py` with `--strict-git`, `--output`, `--skip-relevance` flags per FR-002a/FR-002b
- [X] T045 [US1] Log MLflow parent repro run params (`release_tag`, `git_sha`, `custom_judge_version`, `relevance_labels_hash`, per-variant child runs) in `src/evaluation/reproduction/runner.py` per FR-012
- [X] T046 [US1] Enforce paper-v1.0 five-variant list and full `dev` split (no `--max-items` unless smoke manifest) in `src/evaluation/reproduction/manifest.py` validation

**Checkpoint**: `uv run pytest tests/integration/test_repro_smoke.py -q` passes; smoke `run-all` produces verified tables

---

## Phase 7: User Story 5 - Frozen Corpus Rebuild from Release Manifest (Priority: P3)

**Goal**: Third party restores bundled corpus from manifest + LFS only; fail-fast on missing objects

**Note**: Core verify-corpus behavior is implemented in Phase 2 (T013–T015). This phase adds US5-specific integration coverage and operator UX only.

**Independent Test**: Clean checkout + `git lfs pull` + `verify-corpus` passes; missing LFS object yields explicit artifact list

### Tests for User Story 5

- [X] T047 [P] [US5] Add integration test `tests/integration/test_repro_corpus_rebuild.py` verifying hash match on fixture after simulated clean verify per US5 acceptance scenario 1

### Implementation for User Story 5

- [X] T048 [US5] Enhance `src/evaluation/reproduction/corpus_verify.py` missing-object messages with `git lfs pull --include=…` hints per US5 acceptance scenario 1
- [X] T049 [US5] Add dry-run eval preflight in `repro verify-corpus` loading custom-judge registry split header without executing items in `src/cli/commands/repro.py`

**Checkpoint**: US5 integration test passes; quickstart step 1 documented behavior verified

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs, CI, reference bounds, paper tag readiness

- [X] T050 [P] Update `docs/benchmark-reproduction.md` to point to `specs/012-research-repro-kit/quickstart.md` for paper-v1.0 per plan Phase E
- [X] T051 [P] Add README section for research reproduction (`agent-query repro run-all`) in `README.md` with time/compute bounds per FR-013
- [X] T052 Add CI job step running `uv run pytest tests/integration/test_repro_smoke.py -q` in `.github/workflows/ci.yml` per FR-014
- [X] T053 Document reference machine profile (8 vCPU, 32 GB, LFS size) in `specs/012-research-repro-kit/quickstart.md` per `research.md` R9
- [ ] T054 Populate `releases/paper-v1.0/expected_checksums.json` when custom-judge v1.0.0 is published and baseline repro completes (operator task)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US2 (Phase 3)**: Depends on Foundational — blocks full ranking metrics in US3/US1
- **US3 (Phase 4)**: Depends on Foundational; US2 recommended before ranking validation
- **US4 (Phase 5)**: Depends on US3 producing variant run outputs
- **US1 (Phase 6)**: Depends on US2, US3, US4, Foundational (integrates all)
- **US5 (Phase 7)**: Depends on Foundational only — can parallel with US2–US4 after Phase 2
- **Polish (Phase 8)**: Depends on US1 smoke path green

### User Story Dependencies

| Story | Priority | Depends on | Independent test |
|-------|----------|------------|------------------|
| US1 | P1 | US2, US3, US4 | `run-all` smoke integration |
| US2 | P1 | Phase 2 | `materialize-relevance` stable hash |
| US3 | P2 | Phase 2 (+ US2 for ranking) | Five-variant smoke run (≤20 items) |
| US4 | P2 | US3 run outputs | Export CSV schema |
| US5 | P3 | Phase 2 | `verify-corpus` hash gate |

**Priority vs phase order**: US1 is **P1 in the spec** but **Phase 6 in tasks** by design—it integrates US2–US4; implement US2 → US3 → US4 before US1 `run-all`.

### Parallel Opportunities

- Phase 1: T003–T007 all [P]
- Phase 2: T009–T012, T015–T017 all [P]
- After Phase 2: **US2 and US5** can proceed in parallel
- After US3: **US4** export tests (T035–T036) parallel with structural work if runner done
- US1 integration tests T041–T042 parallel

### Parallel Example: User Story 3

```bash
# Models and tests in parallel:
Task T024: tests/unit/test_flat_chunk_baseline.py
Task T025: tests/unit/test_variant_profile.py
Task T026: tests/unit/test_structural_metrics.py
Task T027: src/retrieval/orchestration/variant_profile.py
```

---

## Implementation Strategy

### MVP First (User Story 1 smoke path)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US2 (relevance on fixture)
4. Complete Phase 4: US3 (graph-full + flat-chunk smoke)
5. Complete Phase 5: US4 (export tables)
6. Complete Phase 6: US1 (`run-all` integration test)
7. **STOP and VALIDATE**: CI smoke ≤15 min

### Incremental Delivery

1. Setup + Foundational → offline verify works
2. US2 → graph-grounded labels on bundle
3. US3 → variant comparison on 20 items
4. US4 → paper tables export
5. US1 → full orchestration
6. US5 + Polish → third-party repro docs and CI

### Full Paper Reproduction (post-011 publish)

- Publish custom-judge v1.0.0 (≥200 items)
- Run materialize-relevance on published bundle
- Execute `run-all` with live judge/LLM at `paper-v1.0` tag
- Record checksums in T054

---

## Notes

- Headline eval MUST NOT invoke FinDER, FinanceBench, or FinAgentBench adapters (FR-003)
- `paper-v1.0` requires exactly five variants and full `dev` split (FR-005a, FR-002b)
- Flat-chunk stays in evaluation layer; ablations use declarative flags only in retrieval graph
- `paper-smoke` and `paper-v1.0` manifests MUST list all five variant ids (item cap allowed for smoke only)
- Commit after each phase checkpoint; run `uv run pytest` before marking tasks complete
