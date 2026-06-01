---
description: "Task list for benchmark evaluation acceleration (013)"
---

# Tasks: Benchmark Evaluation Acceleration

**Input**: Design documents from `specs/013-benchmark-eval-acceleration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **012** (repro kit, merged), **010** (trajectory judge), **011** (custom-judge) on branch `013-benchmark-eval-acceleration`

**Tests**: Unit and integration tests per plan testing strategy and success criteria SC-001–SC-007.

**Organization**: Foundational model/IO extensions block all stories; **US1 defer judge → US2 per-item subgraph → US3 resume/recovery**; polish adds CI and docs. US2 and US1 both touch `runner.py` — implement US1 first to reduce merge conflicts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/evaluation/reproduction/runner.py`, `snapshot_loader.py`, `export.py`, `flat_chunk.py`, `src/retrieval/service.py`, `src/cli/commands/repro.py`, `src/models/evaluation.py`, `src/models/reproduction.py`
- New: `src/evaluation/reproduction/accession_index.py`, `judge_batch.py`, `io.py`, `errors.py`
- Docs: `docs/research-reproduction.md`
- Tests: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repro acceleration module scaffold and typed errors

- [ ] T001 Create `src/evaluation/reproduction/errors.py` with `MissingBindingsError` and `MissingAccessionsError(item_id, accessions)` per `contracts/item-subgraph.md`
- [ ] T002 [P] Export new public symbols from `src/evaluation/reproduction/__init__.py` per `plan.md` project structure

**Checkpoint**: Imports from `evaluation.reproduction.errors` resolve

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models and atomic checkpoint I/O — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T003 Add `JudgeStatus.PENDING = "pending"` in `src/models/evaluation.py` per `data-model.md`
- [ ] T004 Extend `BenchmarkResult` with optional `trajectory_snapshot: dict` and `generation_mlflow_run_id: str` in `src/models/evaluation.py` per `contracts/defer-judge.md`
- [ ] T005 Extend `ReproRun` with `current_variant`, `completed_variants`, `items_completed`, `defer_judge`, `judge_phase_status`, `last_error` in `src/models/reproduction.py` per `data-model.md`
- [ ] T006 [P] Add `DeferJudgeConfig` model (`enabled`, `judge_after`, `concurrency`, `allow_pending_export`) in `src/models/reproduction.py` per `data-model.md`
- [ ] T007 Implement `write_json_atomic(path, data)` in `src/evaluation/reproduction/io.py` (temp file + rename) per `contracts/repro-resume-cli.md` and spec edge cases
- [ ] T008 [P] Add unit test `tests/unit/test_repro_atomic_write.py` for atomic `results.json` and `repro_run.json` updates
- [ ] T009 [P] Add unit test `tests/unit/test_benchmark_result_pending.py` validating `judge_status=pending` serialization in `src/models/evaluation.py`

**Checkpoint**: `uv run pytest tests/unit/test_repro_atomic_write.py tests/unit/test_benchmark_result_pending.py -q` passes

---

## Phase 3: User Story 1 - Deferred and Batched Judging (Priority: P1) 🎯 MVP

**Goal**: Generation phase runs agents without per-item Gemini; judge-batch scores pending items with restart support

**Independent Test**: 20-item smoke with `--defer-judge` completes generation with zero judge calls in item loop; `judge-batch` restart after simulated failure only processes remaining items (SC-001, SC-002)

### Tests for User Story 1

- [ ] T010 [P] [US1] Add unit tests `tests/unit/test_defer_judge.py` for `QueryService` skip-audit guard (`defer_judge` + `benchmark_item` metadata) per `contracts/defer-judge.md`
- [ ] T011 [P] [US1] Add unit tests `tests/unit/test_judge_batch.py` for idempotent skip of final `judge_status` and merge into `results.json` in `src/evaluation/reproduction/judge_batch.py`
- [ ] T012 [P] [US1] Add unit tests `tests/unit/test_export_pending_judge.py` for headline exclusion of `pending` rows in `src/evaluation/reproduction/export.py`

### Implementation for User Story 1

- [ ] T013 [US1] Add `defer_judge` session config resolver (env `REPRO_DEFER_JUDGE`, CLI `--defer-judge`) in `src/evaluation/reproduction/runner.py` per `research.md` R1
- [ ] T014 [US1] Implement defer guard in `src/retrieval/service.py`: skip `run_post_query_audit` when defer + `benchmark_item` metadata; return `judge_status=pending` per `research.md` R9
- [ ] T015 [US1] Persist `trajectory_snapshot` and `generation_mlflow_run_id` on deferred `QueryResponse` / `BenchmarkResult` in `src/retrieval/service.py` and `src/evaluation/reproduction/runner.py` per `contracts/defer-judge.md`
- [ ] T016 [US1] Update `_score_graph_item` in `src/evaluation/reproduction/runner.py` to set metadata `defer_judge=true`, skip inline `GeminiJudgePanel.judge` when defer enabled
- [ ] T017 [US1] Update `_score_flat_chunk_item` in `src/evaluation/reproduction/runner.py` to skip inline judge when defer enabled per FR-001 story acceptance 4
- [ ] T018 [US1] Implement `src/evaluation/reproduction/judge_batch.py` with `run_judge_batch(output_dir, variant_id?, concurrency)` using `with_transient_retry` per `research.md` R8
- [ ] T019 [US1] Wire judge-batch after each variant (default) or after all variants via `REPRO_JUDGE_AFTER` in `src/evaluation/reproduction/runner.py` per `research.md` R2
- [ ] T020 [US1] Use `write_json_atomic` for judge-batch `results.json` updates in `src/evaluation/reproduction/judge_batch.py`
- [ ] T021 [US1] Extend `export_paper_tables` / `build_variant_summary` in `src/evaluation/reproduction/export.py` to exclude `judge_status=pending` and audit-count them per `research.md` R7
- [ ] T022 [US1] Gate `run_all` table export until no pending judges unless `--allow-pending-export` in `src/evaluation/reproduction/runner.py`
- [ ] T023 [US1] Add CLI flags `--defer-judge`, `--judge-only`, `--allow-pending-export`, `--judge-batch-after` on `run`, `run-all` in `src/cli/commands/repro.py` per `contracts/repro-resume-cli.md`
- [ ] T024 [US1] Add `repro judge-batch` subcommand in `src/cli/commands/repro.py` with `--output`, `--variant`, `--concurrency` per `contracts/repro-resume-cli.md`
- [ ] T025 [US1] Add `tests/integration/test_repro_defer_judge_smoke.py`: (a) `test_defer_judge_ci_smoke` — 5 items, mock judge/LLM, asserts zero `run_post_query_audit` / inline `GeminiJudgePanel.judge` during generation then batch completes (SC-001 CI gate); (b) `test_defer_judge_sc001_twenty_items` — `@pytest.mark.slow`, 20 items, same zero-inline-judge assertion (SC-001 release validation)
- [ ] T026 [US1] Add `tests/integration/test_repro_judge_batch_restart.py`: seed 20-item `results.json` with `judge_status=pending`, run judge-batch through 10 items (mock judge recording call count), simulate crash (stop before 11–20), re-run batch; assert items 1–10 `judge_verdict` unchanged and items 11–20 judged exactly once (SC-002)

**Checkpoint**: `uv run pytest tests/unit/test_defer_judge.py tests/unit/test_judge_batch.py tests/integration/test_repro_defer_judge_smoke.py tests/integration/test_repro_judge_batch_restart.py -q` passes; `uv run pytest -m slow tests/integration/test_repro_defer_judge_smoke.py -q` for SC-001 scale

---

## Phase 4: User Story 2 - Per-Item Graph Scope (Priority: P1)

**Goal**: Each benchmark item loads only issuer snapshots from `expected_bindings`, with cache reuse and fail-fast on missing accessions

**Independent Test**: Single-issuer item graph node count ≤ issuer snapshot size; 10-item smoke shows ≥25% median time improvement vs composite baseline (SC-003, SC-004)

### Tests for User Story 2

- [ ] T027 [P] [US2] Add unit tests `tests/unit/test_accession_index.py` for accession→(ticker, snapshot_id) mapping and ambiguous/missing errors in `src/evaluation/reproduction/accession_index.py`
- [ ] T028 [P] [US2] Add unit tests `tests/unit/test_item_subgraph.py` for `load_item_subgraph` merge and empty-bindings fail-fast in `src/evaluation/reproduction/snapshot_loader.py`
- [ ] T029 [P] [US2] Add integration test `tests/integration/test_repro_item_subgraph.py` for single-issuer node cap and two-issuer evidence on smoke fixture per SC-003/SC-004

### Implementation for User Story 2

- [ ] T030 [US2] Implement `AccessionIndex.build(bundle_root)` in `src/evaluation/reproduction/accession_index.py` per `contracts/item-subgraph.md`
- [ ] T031 [US2] Add `load_item_subgraph(bundle_root, accessions, index)` returning `(slice_id, GraphSnapshot)` in `src/evaluation/reproduction/snapshot_loader.py`; keep `load_bundle_snapshot` for relevance only per `research.md` R4
- [ ] T032 [US2] Add slice cache `dict[frozenset[str], GraphSnapshot]` on `ReproRunner` in `src/evaluation/reproduction/runner.py` per `research.md` R5
- [ ] T033 [US2] Refactor graph variant loop to build per-item `InMemoryGraphQueryAPI(slice)` and `QueryService(graph_api=..., issuer_id=slice.issuer_id)` in `src/evaluation/reproduction/runner.py` per FR-008
- [ ] T034 [US2] Filter `pre_bound_filings` from slice manifest (not composite) in `_score_graph_item` in `src/evaluation/reproduction/runner.py`
- [ ] T035 [US2] Fail fast on empty `expected_bindings.accessions` with `MissingBindingsError` in `src/evaluation/reproduction/runner.py` per spec edge cases
- [ ] T036 [US2] Fail fast on unknown accessions with `MissingAccessionsError` in `src/evaluation/reproduction/accession_index.py` per FR-009
- [ ] T037 [US2] Log per-item progress line with issuers, node count, filing count in `src/evaluation/reproduction/runner.py` per FR-011
- [ ] T038 [US2] Restrict `FlatChunkBaseline` chunk corpus to slice snapshots (cache key includes accession set) in `src/evaluation/reproduction/flat_chunk.py` per `contracts/item-subgraph.md`
- [ ] T039 [US2] Add optional benchmark script or documented `scripts/repro_subgraph_bench.sh` comparing 10-item median time composite vs slice per SC-003 (CI optional)

**Checkpoint**: Subgraph unit/integration tests pass; progress logs show single-ticker loads for single-issuer items

---

## Phase 5: User Story 3 - Resumable Full Reproduction (Priority: P1)

**Goal**: Variant-level and run-level resume, export-only recovery, operator playbook

**Independent Test**: Kill after 5 items → resume completes without duplicate `item_id`; kill between variants → completed variant skipped; `export-only` produces tables with audit for missing work (SC-005, SC-006, SC-007)

### Tests for User Story 3

- [ ] T040 [P] [US3] Add unit tests `tests/unit/test_repro_variant_skip.py` for variant complete detection (item count + no pending judge when defer) in `src/evaluation/reproduction/runner.py`
- [ ] T041 [P] [US3] Add integration test `tests/integration/test_repro_resume.py` for item-level and variant-level resume per SC-005/SC-006
- [ ] T042 [P] [US3] Add integration test `tests/integration/test_repro_export_only.py` for partial variant export with audit rows per SC-007

### Implementation for User Story 3

- [ ] T043 [US3] Load and update `repro_run.json` atomically after each item and variant boundary in `src/evaluation/reproduction/runner.py` per FR-015
- [ ] T044 [US3] Implement variant-level skip in `run_all` / `run_variant` when variant `results.json` complete and judge phase done in `src/evaluation/reproduction/runner.py` per FR-013
- [ ] T045 [US3] Add `--resume` (default true) and `--no-resume` flags on `run-all` and `run` in `src/cli/commands/repro.py` per `contracts/repro-resume-cli.md`
- [ ] T046 [US3] Document `--no-resume` wipe policy (delete output dir or variant subdirs) in `docs/research-reproduction.md` per FR-017
- [ ] T047 [US3] Implement `export_tables_from_disk(manifest, input_dir)` replacing stub in `src/evaluation/reproduction/runner.py` and wire `repro export-tables` in `src/cli/commands/repro.py` per FR-016
- [ ] T048 [US3] Add `run-all --export-only` path skipping corpus verify and variant execution in `src/evaluation/reproduction/runner.py`
- [ ] T049 [US3] Formalize relevance skip when sidecar coverage ≥90% with regression test in `tests/unit/test_relevance_skip_gate.py` referencing `src/evaluation/reproduction/runner.py` per spec US3 acceptance 4
- [ ] T050 [US3] Add recovery playbook section to `docs/research-reproduction.md` (interrupt, verify `jq length`, resume, judge-batch, reset variant dir) per FR-017 and `quickstart.md`
- [ ] T051 [US3] Update `specs/013-benchmark-eval-acceleration/quickstart.md` cross-links if CLI flag names differ after implementation

**Checkpoint**: Resume and export-only integration tests pass; operator can follow docs to recover a partial `reports/repro-paper-v1.0/` run

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end smoke, CI, README

- [ ] T052 [P] Add integration test `tests/integration/test_repro_acceleration_smoke.py` combining defer + subgraph + resume on `releases/paper-smoke` (≤5 items, mocks) per plan testing strategy
- [ ] T053 [P] Extend `.github/workflows/ci.yml` to run new 013 unit tests, `test_repro_defer_judge_smoke.py`, and `test_repro_judge_batch_restart.py` in reproduction job (exclude `@pytest.mark.slow` by default)
- [ ] T054 [P] Register `slow` marker in `pyproject.toml` for SC-001 20-item test; document `pytest -m slow` in `quickstart.md`
- [ ] T055 [P] Update `README.md` research reproduction section with `--defer-judge`, `--resume`, and expected wall-clock improvements pointer to `docs/research-reproduction.md`
- [ ] T056 Run `uv run pytest tests/unit/test_*repro* tests/integration/test_repro_* -q` and fix any regressions against 012 smoke paths

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP**; no dependency on US2/US3
- **US2 (Phase 4)**: Depends on Foundational; **recommended after US1** (shared `runner.py`)
- **US3 (Phase 5)**: Depends on Foundational + US1 (variant skip uses judge pending semantics); export-only depends on US1 export gating
- **Polish (Phase 6)**: Depends on US1–US3

### User Story Dependencies

| Story | Priority | Depends on | Independent test |
|-------|----------|------------|------------------|
| US1 | P1 | Phase 2 | Defer smoke: zero inline judge; judge-batch idempotent |
| US2 | P1 | Phase 2 (+ US1 for same runner) | Subgraph node count + timing smoke |
| US3 | P1 | Phase 2, US1 | Resume + export-only integration |

### Within Each User Story

- Tests before or in parallel with implementation per file
- Models (Phase 2) before services
- `judge_batch.py` before CLI `judge-batch`
- `accession_index.py` before `load_item_subgraph` before runner loop refactor

### Parallel Opportunities

- Phase 1: T002 [P]
- Phase 2: T006, T008, T009 all [P]
- US1 tests: T010–T012 [P] before implementation batch
- US2 tests: T027–T029 [P]; T030 index parallel with T031 loader if coordinated
- US3 tests: T040–T042 [P]
- Polish: T052–T055 [P]

### Parallel Example: User Story 1

```bash
# Tests in parallel:
tests/unit/test_defer_judge.py
tests/unit/test_judge_batch.py
tests/unit/test_export_pending_judge.py

# After T013–T015, judge batch module parallel with export changes:
src/evaluation/reproduction/judge_batch.py
src/evaluation/reproduction/export.py
```

### Parallel Example: User Story 2

```bash
# Index + loader tests in parallel:
tests/unit/test_accession_index.py
tests/unit/test_item_subgraph.py

# Implementation sequence:
src/evaluation/reproduction/accession_index.py
src/evaluation/reproduction/snapshot_loader.py  # then runner + flat_chunk
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (defer judge + judge-batch)
4. **STOP and VALIDATE**: `test_repro_defer_judge_smoke.py` and manual `run-all --defer-judge --max-items 5` on paper-smoke

### Incremental Delivery

1. Setup + Foundational → atomic IO and pending status ready
2. US1 → faster generation phase (judge decoupled)
3. US2 → smaller graphs per item (~25%+ speedup target)
4. US3 → overnight-run recovery and export-only
5. Polish → CI and combined smoke

### Full Paper Reproduction (operator)

```bash
export OFFLINE_BENCHMARK=1 REPRO_DEFER_JUDGE=1 USE_MOCK_JUDGE=0 USE_MOCK_LLM=0
uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --defer-judge --resume
```

---

## Notes

- Do **not** change interactive `agent-query ask` when defer env is set without `benchmark_item` metadata (constitution guard)
- Relevance materialize continues to use full composite via `load_bundle_snapshot` (012 unchanged)
- Option A (benchmark-fast macro skip) is **out of scope**
- Commit after each phase checkpoint; run targeted pytest before marking tasks complete
