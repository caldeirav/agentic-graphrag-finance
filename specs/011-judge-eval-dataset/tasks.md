---
description: "Task list for judge-generated custom evaluation dataset (011)"
---

# Tasks: Judge-Generated Custom Evaluation Dataset

**Input**: Design documents from `specs/011-judge-eval-dataset/`

**Prerequisites**: plan.md, spec.md (with clarifications), research.md, data-model.md, contracts/, quickstart.md; features 010 (judge), 004 (materialization), 001 (benchmark registry) on branch `011-judge-eval-dataset`

**Tests**: Contract, unit, and integration tests per plan testing strategy and spec success criteria (SC-001–SC-007).

**Organization**: Foundational typed models block all stories; **US1 sampling → US2 materialize → US3 judge generate** form the generation core; **US4 publish/registry** enables eval; **US5 reproduce/extend** completes reproducibility.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/evaluation/generation/`, `src/models/benchmark_generation.py`, `src/cli/benchmark_materialize.py`, `src/evaluation/datasets/custom_judge.py`, `src/cli/commands/benchmark_dataset.py`, `configs/benchmarks/`, `data/benchmarks/custom-judge/`, `scripts/build_issuer_allowlist.py`
- Extend: `src/models/evaluation.py`, `src/evaluation/registry.py`, `src/evaluation/runner.py`, `src/cli/main.py`, `.gitattributes`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config stubs, package scaffold, LFS rules, allowlist builder

- [X] T001 Create `src/evaluation/generation/__init__.py` exporting public generation API stubs per `plan.md`
- [X] T002 [P] Add Git LFS rules for `data/benchmarks/custom-judge/**/corpus/**` in `.gitattributes` per `research.md` R6
- [X] T003 [P] Add `configs/benchmarks/custom_judge_v1.yaml` with equal-thirds quotas and governance defaults per `contracts/generation-config-schema.md`
- [X] T004 [P] Add inspiration profiles `configs/benchmarks/inspiration_profiles/financebench.yaml`, `finder.yaml`, `finagentbench.yaml` per `research.md` R4
- [X] T005 [P] Add `scripts/build_issuer_allowlist.py` writing `configs/benchmarks/issuer_allowlist_v1.json` per `research.md` R1
- [X] T006 [P] Add `configs/benchmarks/custom_judge_ci.yaml` tiny config for CI/mock generation in `tests/fixtures/custom_judge/`
- [X] T007 Register Typer command group stub `benchmark-dataset` in `src/cli/main.py` pointing to `src/cli/commands/benchmark_dataset.py`

**Checkpoint**: `uv run agent-query benchmark-dataset --help` lists `generate`, `publish`, `reproduce`, `extend` (stubs OK)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic types, config loader, governance, import-boundary tests — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [X] T008 [P] Add `GenerationConfig`, `GovernanceCaps`, `IssuerAllowlist`, `SamplingManifest`, `CorpusBundle`, `DatasetManifest`, `GenerationReport`, `GeneratedBenchmarkItem` in `src/models/benchmark_generation.py` per `data-model.md`
- [X] T009 [P] Extend `BenchmarkItem` with `expected_section_paths: list[str]` in `src/models/evaluation.py` per `contracts/custom-judge-dataset-adapter.md`
- [X] T010 [P] Implement `src/evaluation/generation/governance.py` with budget counters and fail-stop per FR-007
- [X] T011 [P] Implement `src/evaluation/generation/config_loader.py` loading YAML into `GenerationConfig` with quota-sum validation
- [X] T012 [P] Export new models from `src/models/__init__.py`
- [X] T013 [P] Add contract test `tests/contract/test_generation_import_boundary.py` forbidding retrieval imports in `src/evaluation/generation/` per `contracts/judge-generation-boundary.md`
- [X] T014 [P] Add contract test `tests/contract/test_custom_judge_manifest.py` validating golden manifest JSON against Pydantic models per `contracts/dataset-bundle-manifest.md`
- [X] T015 [P] Create `tests/fixtures/custom_judge/` with minimal draft manifest, 3-item JSONL, and mock `corpus/graph_node_index.json`
- [X] T016 [P] Add unit test `tests/unit/test_generation_config_loader.py` for quota validation and allowlist hash in `src/evaluation/generation/config_loader.py`
- [X] T017 [P] Implement production mock guard in `src/cli/commands/benchmark_dataset.py`: reject `--mock-judge` and `USE_MOCK_JUDGE=1` unless `GenerationConfig.config_id` is `custom_judge_ci` per FR-014

**Checkpoint**: `uv run pytest tests/contract/test_generation_import_boundary.py tests/unit/test_generation_config_loader.py -q` passes

---

## Phase 3: User Story 1 - Reproducible Issuer and Filing Sampling (Priority: P1) 🎯 MVP

**Goal**: Seed-random issuer/filing selection from committed allowlist with persisted `sampling_manifest.json` and budget pre-check

**Independent Test**: Run sampler twice with same config/seed; identical manifest hash; budget exceeded stops before ingestion

### Tests for User Story 1

- [X] T018 [P] [US1] Add unit tests `tests/unit/test_generation_sampler.py` for deterministic issuer draw, accession selection, and manifest hash stability

### Implementation for User Story 1

- [X] T019 [US1] Implement `src/evaluation/generation/sampler.py` with allowlist load, seed-random issuer sample, filing filters, and rationale tags per FR-001/FR-016
- [X] T020 [US1] Write canonical `sampling_manifest.json` (sorted keys, content hash) from sampler in `src/evaluation/generation/sampler.py`
- [X] T021 [US1] Integrate governance preflight in `src/evaluation/generation/sampler.py` to fail before ingestion when caps exceeded per US1 acceptance scenario 3
- [X] T022 [US1] Wire `generate` subcommand **phase 1 (sampling only)** in `src/cli/commands/benchmark_dataset.py` writing draft dir under `data/benchmarks/custom-judge/drafts/{run_id}/`; phases 2–3 complete full pipeline to draft in T028 and T037 (FR-011)

**Checkpoint**: US1 unit tests pass; repeated sampling yields identical `sampling_manifest.json` hash (`generate` stops after phase 1 until T028/T037)

---

## Phase 4: User Story 2 - Production Pipeline Materialization (Priority: P1)

**Goal**: Materialize sampled filings via `cli.corpus_pipeline.run_materialize_pipeline`; bundle corpus artifacts and graph node index

**Independent Test**: Materialize 3 issuers / 5 filings; snapshot ids present; artifacts under draft `corpus/`; no eval-time EDGAR

### Tests for User Story 2

- [X] T023 [P] [US2] Add unit test `tests/unit/test_benchmark_materialize.py` mocking `run_materialize_pipeline` and asserting per-issuer snapshot refs in `src/cli/benchmark_materialize.py`

### Implementation for User Story 2

- [X] T024 [US2] Implement `src/cli/benchmark_materialize.py` with `materialize_sampled_corpus()` calling `cli.corpus_pipeline.run_materialize_pipeline` per issuer; invoked only from `src/cli/commands/benchmark_dataset.py` per `contracts/judge-generation-boundary.md`
- [X] T025 [US2] Copy/link graph snapshots and raw SEC packages into draft `corpus/` tree in `src/cli/benchmark_materialize.py` per `data-model.md` CorpusBundle layout
- [X] T026 [US2] Export `corpus/graph_node_index.json` from materialized snapshots in `src/cli/benchmark_materialize.py` for section-path validation
- [X] T027 [US2] Record ingestion failures in draft `generation_report.json` without producing items for failed accessions per US2 acceptance scenario 3
- [X] T028 [US2] Wire materialize as **`generate` phase 2** after sampling in `src/cli/commands/benchmark_dataset.py`

**Checkpoint**: Small mock/materialize integration produces draft dir with `corpus/` + `graph_node_index.json`

---

## Phase 5: User Story 3 - Judge-Assisted Question Generation (Priority: P1)

**Goal**: Gemini generates items per inspiration profile with quotas; validator rejects bad section paths; dedup + checkpoint resume

**Independent Test**: Generate for one issuer; each accepted item has question, ground truth/rubric, expected filings, resolvable section paths

### Tests for User Story 3

- [X] T029 [P] [US3] Add unit tests `tests/unit/test_item_validator.py` for path resolution and profile-specific rules in `src/evaluation/generation/item_validator.py`
- [X] T030 [P] [US3] Add unit tests `tests/unit/test_deduplicator.py` for similarity threshold dedup in `src/evaluation/generation/deduplicator.py`
- [X] T031 [P] [US3] Add unit test `tests/unit/test_judge_generator_mock.py` with `USE_MOCK_JUDGE=1` asserting profile tags and JSON shape in `src/evaluation/generation/judge_generator.py`

### Implementation for User Story 3

- [X] T032 [US3] Implement `src/evaluation/generation/judge_generator.py` using Gemini client from `src/evaluation/judges/gemini_panel.py` with separate prompts from `configs/benchmarks/inspiration_profiles/*.yaml` per FR-005
- [X] T033 [US3] Implement quota scheduler (equal-thirds default) selecting profile per candidate in `src/evaluation/generation/judge_generator.py`
- [X] T034 [US3] Implement `src/evaluation/generation/item_validator.py` resolving `expected_section_paths` against `graph_node_index.json` per FR-009
- [X] T035 [US3] Implement `src/evaluation/generation/deduplicator.py` with configurable similarity threshold from governance config
- [X] T036 [US3] Add checkpoint/resume state (`candidates.jsonl`, accepted ids) with judge API backoff in `src/evaluation/generation/judge_generator.py` per US5 acceptance scenario 3
- [X] T037 [US3] Wire judge+validate as **`generate` phase 3** in `src/cli/commands/benchmark_dataset.py`: write accepted items to `items/dev.jsonl`, update `generation_report.json` pass rate, finalize draft manifest — completes FR-011 full pipeline to draft

**Checkpoint**: Mock judge `generate` produces ≥5 validated items in draft; validator rejects hallucinated paths; all three generate phases run end-to-end

---

## Phase 6: User Story 4 - Versioned Bundle and Registry Plug-In (Priority: P2)

**Goal**: Draft bundle assembly, explicit publish, `custom-judge` registry adapter, offline eval graph root override

**Independent Test**: Publish fixture draft; registry loads dev split; eval with `OFFLINE_BENCHMARK=1` uses bundled snapshot (no EDGAR)

### Tests for User Story 4

- [X] T038 [P] [US4] Add contract test `tests/contract/test_custom_judge_dataset_adapter.py` for JSONL→`BenchmarkItem` mapping and no synthetic fallback in `src/evaluation/datasets/custom_judge.py`
- [X] T039 [P] [US4] Add unit test `tests/unit/test_generation_bundle_hash.py` for deterministic `items_hash` in `src/evaluation/generation/bundle.py`

### Implementation for User Story 4

- [X] T040 [US4] Implement draft assembly and manifest writer (`status: draft`) in `src/evaluation/generation/bundle.py` per `contracts/dataset-bundle-manifest.md`
- [X] T041 [US4] Implement `publish` promoting draft to `data/benchmarks/custom-judge/v{version}/` with `status: published` and both judge pins in `src/cli/commands/benchmark_dataset.py`
- [X] T042 [US4] Enforce publish gates (≥95% pass rate, ≥200 items for v1) in `src/evaluation/generation/bundle.py` before promotion per FR-014
- [X] T043 [US4] Implement `src/evaluation/datasets/custom_judge.py` loading published bundle with LFS path resolution per `contracts/custom-judge-dataset-adapter.md`
- [X] T044 [US4] Register `custom-judge` in `src/evaluation/registry.py` `default_registry()` with `CUSTOM_JUDGE_VERSION` env override
- [X] T045 [US4] Extend `src/evaluation/runner.py` to accept bundled graph root override and set `OFFLINE_BENCHMARK=1` preflight when dataset is `custom-judge`
- [X] T046 [US4] Log MLflow benchmark params `custom_judge_version`, `items_hash`, `snapshot_id`, `generation_seed`, `generation_judge_version`, and `evaluation_judge_version` on parent run in `src/evaluation/runner.py` per FR-015

**Checkpoint**: Registry loads published fixture; runner refuses EDGAR when offline flag set

---

## Phase 7: User Story 5 - CLI Reproduce and Extend (Priority: P2)

**Goal**: Reproduce manifest hash offline; extend parent version with delta config and immutable parent artifacts

**Independent Test**: `reproduce --version` matches hash; `extend` produces draft with `parent_version` and added items

### Tests for User Story 5

- [X] T047 [P] [US5] Add integration test `tests/integration/test_custom_judge_reproduce_hash.py` verifying hash match on fixture bundle without network

### Implementation for User Story 5

- [X] T048 [US5] Implement `reproduce` subcommand recomputing `items_hash` and verifying LFS `artifact_hashes` in `src/cli/commands/benchmark_dataset.py` per `contracts/dataset-generation-cli.md`
- [X] T049 [US5] Implement `extend` subcommand copying parent items and merging delta sampling in `src/cli/commands/benchmark_dataset.py` with `parent_version` in manifest per `research.md` R8
- [X] T050 [US5] Document snapshot reuse vs new composite snapshot rules for extend in `src/evaluation/generation/bundle.py` per edge case in spec

**Checkpoint**: US5 integration test passes on committed fixture; extend draft shows parent linkage

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end smoke, docs, operator publish gate

- [ ] T051 [P] Add integration test `tests/integration/test_custom_judge_offline_eval.py` running ≥20 items with `USE_MOCK_LLM=1` `USE_MOCK_JUDGE=1` per SC-006
- [X] T052 [P] Add `configs/benchmarks/custom_judge_v1_extend.yaml` example for extend workflow in `specs/011-judge-eval-dataset/quickstart.md`
- [X] T053 [P] Add README subsection linking to `specs/011-judge-eval-dataset/quickstart.md` under benchmark/evaluation docs in `README.md`
- [ ] T054 Run full `specs/011-judge-eval-dataset/quickstart.md` validation on fixture bundle (reproduce + smoke eval steps)
- [ ] T055 **Operator gate**: Run full `generate` + operator `publish --version 1.0.0` with real Gemini/EDGAR; confirm ≥200 items and commit LFS corpus (manual, documented in quickstart)

**Checkpoint**: SC-001–SC-007 satisfied for v1.0.0 publish (T055 manual)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on US1 (needs sampling manifest)
- **US3 (Phase 5)**: Depends on US2 (needs corpus + node index)
- **US4 (Phase 6)**: Depends on US3 (needs accepted items)
- **US5 (Phase 7)**: Depends on US4 (needs published bundle contract)
- **Polish (Phase 8)**: Depends on US4 minimum; full polish after US5

### User Story Dependencies

```text
US1 (sample) → US2 (materialize) → US3 (judge) → US4 (publish/registry) → US5 (reproduce/extend)
```

US1 alone is the **MVP slice** (deterministic sampling manifest). US1+US2+US3 yields a **draft** dataset. US4 required for evaluation. US5 completes reproducibility story.

### Parallel Opportunities

- Phase 1: T002–T006 parallel after T001
- Phase 2: T008–T017 mostly parallel after T001 package exists
- Within US3: T029–T031 parallel; T034–T035 parallel after T026 node index contract stable
- Within US4: T038–T039 parallel before T040
- Phase 8: T051–T053 parallel

### Parallel Example: User Story 3

```bash
# Tests in parallel:
tests/unit/test_item_validator.py
tests/unit/test_deduplicator.py
tests/unit/test_judge_generator_mock.py

# Then implementation chain:
src/evaluation/generation/judge_generator.py → item_validator.py → deduplicator.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1 sampling)
3. **STOP and VALIDATE**: identical sampling manifest hash on repeat runs

### Incremental Delivery

1. US1 → reproducible sampling manifest
2. + US2 → bundled production corpus in draft
3. + US3 → judge-generated validated items (draft eligible)
4. + US4 → publish + registry + offline eval
5. + US5 → reproduce/extend + full quickstart

### Suggested MVP Scope

**Through US1** for earliest checkpoint; **through US3** for draft dataset review; **through US4** for evaluation integration (SC-006 smoke).

---

## Notes

- Materialization MUST go through `src/cli/benchmark_materialize.py` → `cli.corpus_pipeline` (never `evaluation/generation/*`) per `contracts/judge-generation-boundary.md`
- Disable synthetic fallback for `custom-judge` adapter (FR-010 / SC-002)
- v1 default: same Gemini pin for generation and evaluation (`spec.md` clarifications)
- `[P]` tasks = different files; wire `generate` phases sequentially in `benchmark_dataset.py`: T022 (sample) → T028 (materialize) → T037 (judge/validate draft)
