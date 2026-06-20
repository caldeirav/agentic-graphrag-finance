---
description: "Task list for evaluation dataset quality improvement and management (018)"
---

# Tasks: Evaluation Dataset Quality Improvement and Management

**Input**: Design documents from `specs/018-eval-dataset-quality/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **011–017** merged; branch `018-eval-dataset-quality`; published `data/benchmarks/custom-judge/v2.0.0/` and `reports/repro-paper-v1.0/` available locally

**Tests**: Unit and integration tests per plan testing strategy and success criteria SC-001–SC-007.

**Organization**: Setup → foundational review package + models → **US1 review queue (MVP) → US2 annotations → US3 overrides → US4 diversity loop → US5 comparison boilerplate gate → US6 selective re-judge → US7 review pack** → polish (v2.0.1 publish + paper-v1.1). US1–US3 form the HITL MVP; US6 validates fixes before full paper repro.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/evaluation/generation/review/{queue,annotations,overrides,review_pack,quality_summary,regenerate_item}.py`
- Extend: `src/evaluation/generation/{comparison_gt,deduplicator,judge_generator,bundle,item_validator}.py`
- Extend: `src/evaluation/reproduction/judge_batch.py`, `src/evaluation/reproduction/report_render.py`
- Extend: `src/models/benchmark_generation.py`, `src/cli/commands/{benchmark_dataset,repro}.py`
- New: `configs/benchmarks/custom_judge_v2_quality.yaml`, `releases/paper-v1.1/manifest.yaml`
- Tests: `tests/unit/`, `tests/integration/`, `tests/contract/`

---

## Phase 1: Setup

**Purpose**: Confirm branch baseline and 018 design contracts

- [X] T001 Confirm branch `018-eval-dataset-quality` is rebased on `main` with 017 custom-judge v2.0.0 publish path and `reports/repro-paper-v1.0/` baseline present
- [X] T002 [P] Review normative contracts in `specs/018-eval-dataset-quality/contracts/` against current `src/cli/commands/benchmark_dataset.py` and `src/evaluation/generation/bundle.py`
- [X] T003 [P] Add `configs/benchmarks/custom_judge_v2_quality.yaml` skeleton per `specs/018-eval-dataset-quality/contracts/diversity-governance.md` (extend parent v2.0.0, diversity governance fields)

**Checkpoint**: `uv run pytest tests/unit/test_bundle_feasibility_gates.py tests/unit/test_comparison_gt_template.py -q` passes on feature branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Review package scaffold, shared models, CLI wiring — MUST complete before user story phases

**⚠️ CRITICAL**: Blocks all user stories

- [X] T004 Add `FailureClass`, `ItemAnnotation`, `ReviewQueueEntry`, `OverrideChangelogEntry`, `DuplicateRejectionFeedback`, `DiversityReport`, `QualityPassSummary` models in `src/models/benchmark_generation.py` per `specs/018-eval-dataset-quality/data-model.md`
- [X] T005 [P] Create `src/evaluation/generation/review/__init__.py` and package docstring referencing 011 judge-generation boundary
- [X] T006 [P] Add `review` Typer subcommand group in `src/cli/commands/benchmark_dataset.py` per `specs/018-eval-dataset-quality/contracts/dataset-review-cli.md`
- [X] T007 [P] Add contract test `tests/contract/test_review_import_boundary.py` ensuring `src/evaluation/generation/review/` does not import retrieval or ingestion paths
- [X] T008 [P] Add helper `resolve_draft_bundle(path)` in `src/evaluation/generation/review/_paths.py` for draft/published bundle root validation

**Checkpoint**: `uv run python -c "from models.benchmark_generation import ItemAnnotation; from evaluation.generation.review import __init__"` succeeds

---

## Phase 3: User Story 1 - Reproduction-Driven Review Queue (Priority: P1) 🎯 MVP

**Goal**: Export prioritized review queue from repro results + dev split; tier-1 = MRR ≥ 0.5 or nDCG@10 ≥ 0.3 with outcome score = 0

**Independent Test**: `review export-queue` on `reports/repro-paper-v1.0` ranks high-retrieval/zero-outcome items above low-retrieval items (`specs/018-eval-dataset-quality/contracts/review-queue-export.md`)

### Tests for User Story 1

- [X] T009 [P] [US1] Add unit tests `tests/unit/test_review_queue.py` for tier assignment, sort order, and missing-repro fallback

### Implementation for User Story 1

- [X] T010 [US1] Implement `build_review_queue` and `write_review_queue` in `src/evaluation/generation/review/queue.py` loading `items/dev.jsonl` and `{variant}/results.json`
- [X] T011 [US1] Implement `review export-queue` command in `src/cli/commands/benchmark_dataset.py` with `--draft`, `--repro-input`, `--variant`, `--tier`, `--output` flags
- [X] T012 [P] [US1] Add integration test `tests/integration/test_review_export_queue.py` using fixture repro dir and v2.0.0 bundle subset

**Checkpoint**: `uv run pytest tests/unit/test_review_queue.py -q` passes; tier-1 count > 0 against local `reports/repro-paper-v1.0`

---

## Phase 4: User Story 2 - Per-Item Annotation and Corpus Spot-Check (Priority: P1)

**Goal**: Append-only `annotations.jsonl` sidecar with failure class, notes, corpus spot-check, proposed overrides

**Independent Test**: Annotate 5 items; history preserved; dev.jsonl unchanged until apply (`specs/018-eval-dataset-quality/contracts/annotations-sidecar.md`)

### Tests for User Story 2

- [X] T013 [P] [US2] Add unit tests `tests/unit/test_review_annotations.py` for append-only writes, failure class validation, and history load

### Implementation for User Story 2

- [X] T014 [US2] Implement `append_annotation`, `load_annotation_history`, `latest_annotation` in `src/evaluation/generation/review/annotations.py`
- [X] T015 [US2] Implement `review annotate` command in `src/cli/commands/benchmark_dataset.py` with `--failure-class`, `--corpus-spot-check`, `--proposed-overrides-file`, `--reviewer-id`

**Checkpoint**: `uv run agent-query benchmark-dataset review annotate --help` shows required flags; annotations append without mutating `items/dev.jsonl`

---

## Phase 5: User Story 3 - Human-in-the-Loop Record Overrides (Priority: P1)

**Goal**: Apply approved annotations to dev items in place; `override_changelog.jsonl`; re-run v2 gates; publish path to v2.0.1

**Independent Test**: Extend v2.0.0 draft, apply 3 overrides, changelog + validation gates pass (`specs/018-eval-dataset-quality/spec.md` US3)

### Tests for User Story 3

- [X] T016 [P] [US3] Add unit tests `tests/unit/test_review_overrides.py` for patch merge, parent item hash, and gate failure rollback

### Implementation for User Story 3

- [X] T017 [US3] Implement `apply_overrides` and `write_override_changelog` in `src/evaluation/generation/review/overrides.py` integrating `validate_item` and `validate_bundle_feasibility`
- [X] T018 [US3] Implement `review apply-overrides` command in `src/cli/commands/benchmark_dataset.py` with `--annotation-ids`, `--dry-run`, `--skip-failed`
- [X] T019 [US3] Extend `publish_draft` in `src/evaluation/generation/bundle.py` to support semver `2.0.1`, copy `annotations.jsonl` and `override_changelog.jsonl` to published bundle
- [X] T020 [US3] Add integration test `tests/integration/test_quality_apply_overrides.py` for extend→annotate→apply on fixture draft

**Checkpoint**: Apply 3 overrides on quality draft; `override_changelog.jsonl` has 3 rows; only patched item_ids differ from parent

---

## Phase 6: User Story 4 - Corrective Loop for Generation Diversity (Priority: P2)

**Goal**: `duplicate_feedback.jsonl`, diversity governance config, negative prompt examples, `diversity_report.json`, per-slot `regenerate-item`

**Independent Test**: Judge run writes duplicate feedback; diversity report shows issuer/tag histograms vs v2.0.0 baseline (`specs/018-eval-dataset-quality/contracts/diversity-governance.md`)

### Tests for User Story 4

- [X] T021 [P] [US4] Add unit tests `tests/unit/test_diversity_governance.py` for issuer cap skip and duplicate feedback record shape

### Implementation for User Story 4

- [X] T022 [US4] Extend `src/evaluation/generation/deduplicator.py` and `src/evaluation/generation/judge_generator.py` to append `duplicate_feedback.jsonl` on duplicate rejection per FR-007
- [X] T023 [US4] Add diversity governance fields to `GenerationConfig` / governance model in `src/models/benchmark_generation.py` and `configs/benchmarks/custom_judge_v2.yaml`
- [X] T024 [US4] Implement issuer cap and negative-example injection in `src/evaluation/generation/judge_generator.py` schedule loop per research R5
- [X] T025 [P] [US4] Implement `write_diversity_report` in `src/evaluation/generation/review/diversity.py` (or extend `bundle.py`) emitting `diversity_report.json`
- [X] T026 [US4] Implement `regenerate_item` in `src/evaluation/generation/review/regenerate_item.py` reusing `GeminiItemGenerator` with merged feedback constraints
- [X] T027 [US4] Implement `regenerate-item` command in `src/cli/commands/benchmark_dataset.py` preserving `item_id` on success

**Checkpoint**: Pilot judge run produces `duplicate_feedback.jsonl` and `diversity_report.json`; duplicate rate computable vs v2.0.0 baseline

---

## Phase 7: User Story 5 - Substantive Comparison Ground Truth (Priority: P2)

**Goal**: Reject boilerplate comparison canonical answers; extend scorability report; update finagentbench prompts

**Independent Test**: Intentional boilerplate answers fail validation with `boilerplate_comparison_answer` (`specs/018-eval-dataset-quality/contracts/comparison-boilerplate-gate.md`)

### Tests for User Story 5

- [X] T028 [P] [US5] Add unit tests `tests/unit/test_boilerplate_comparison.py` with reject/accept examples from contract

### Implementation for User Story 5

- [X] T029 [US5] Implement `is_boilerplate_comparison_answer` in `src/evaluation/generation/comparison_gt.py` per contract rules
- [X] T030 [US5] Extend `validate_comparison_structured` in `src/evaluation/generation/comparison_gt.py` to emit `boilerplate_comparison_answer`
- [X] T031 [US5] Extend `write_scorability_report` in `src/evaluation/generation/bundle.py` with `boilerplate_comparison_count` and `borderline_comparison_item_ids`
- [X] T032 [US5] Update `configs/benchmarks/inspiration_profiles/finagentbench.yaml` prompt to require substantive compared conclusion in canonical answer

**Checkpoint**: `uv run pytest tests/unit/test_boilerplate_comparison.py -q` passes; scorability report blocks publish when boilerplate count > 0

---

## Phase 8: User Story 6 - Outcome Improvement Without Full Agent Re-Run (Priority: P2)

**Goal**: Selective `judge-batch` with `--bundle-override` and `--item-ids-file`; `quality_pass_summary.json`

**Independent Test**: Fix 10 items, re-judge graph-full only, majority show improved VA (`specs/018-eval-dataset-quality/quickstart.md` Phase 5)

### Tests for User Story 6

- [X] T033 [P] [US6] Add unit tests `tests/unit/test_quality_summary.py` for dataset-caused zero-score rate and rejudge delta aggregation

### Implementation for User Story 6

- [X] T034 [US6] Extend `run_judge_batch` in `src/evaluation/reproduction/judge_batch.py` to load ground truth from `--bundle-override` path by `item_id`
- [X] T035 [US6] Add `--bundle-override` and `--item-ids-file` flags to `judge-batch` in `src/cli/commands/repro.py`
- [X] T036 [US6] Implement `build_quality_pass_summary` in `src/evaluation/generation/review/quality_summary.py`
- [X] T037 [US6] Implement `review summary` command in `src/cli/commands/benchmark_dataset.py` writing `quality_pass_summary.json`
- [X] T038 [P] [US6] Add integration test `tests/integration/test_selective_rejudge.py` comparing pre/post VA on fixture fixed items

**Checkpoint**: Selective re-judge on 10-item fixture shows `rejudge_improved_rate` in summary JSON

---

## Phase 9: User Story 7 - Review Pack for Efficient Human Audit (Priority: P3)

**Goal**: Export `review_pack.html` + `review_pack.csv` with corpus pointers and optional repro scores

**Independent Test**: 20-item pack export; reviewer completes structural spot-check workflow (`specs/018-eval-dataset-quality/spec.md` SC-001)

### Tests for User Story 7

- [X] T039 [P] [US7] Add unit tests `tests/unit/test_review_pack.py` for CSV/HTML row parity and required columns

### Implementation for User Story 7

- [X] T040 [US7] Implement `build_review_pack_rows` and corpus section excerpt resolver in `src/evaluation/generation/review/review_pack.py`
- [X] T041 [P] [US7] Reuse HTML panel styling from `src/evaluation/reproduction/report_render.py` for `review_pack.html` template
- [X] T042 [US7] Implement `review export-pack` command in `src/cli/commands/benchmark_dataset.py` with `--item-ids-file`, `--max-items`, `--repro-input`, `--output-dir`

**Checkpoint**: Open `review_pack.html` in browser; CSV row count matches HTML item sections

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: paper-v1.1 release, docs, end-to-end quality pass validation

- [X] T043 Add `releases/paper-v1.1/manifest.yaml` template per `specs/018-eval-dataset-quality/contracts/paper-v1.1-release.md` with `parent_release: paper-v1.0` and `custom_judge_version: 2.0.1`
- [X] T044 [P] Update `docs/custom-judge-dataset-generation.md` with quality-pass workflow section linking `specs/018-eval-dataset-quality/quickstart.md`
- [X] T045 [P] Add `specs/018-eval-dataset-quality/checklists/quality-pass.md` operator checklist mirroring quickstart Phases 1–7
- [X] T046 Add end-to-end smoke test `tests/integration/test_quality_pass_smoke.py` using fixtures: queue→annotate→apply dry-run on 3 items
- [X] T047 Run `specs/018-eval-dataset-quality/quickstart.md` Phase 1–5 against local v2.0.0 + repro-paper-v1.0; record tier-1 count and quality summary targets in checklist notes
- [X] T048 [P] Verify `data/benchmarks/custom-judge/v2.0.0/` unchanged after quality draft publish dry-run (`git diff` empty on v2.0.0)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP entry point**
- **US2 (Phase 4)**: Depends on Foundational; integrates with US1 queue item_ids
- **US3 (Phase 5)**: Depends on US2 annotations
- **US4 (Phase 6)**: Depends on Foundational; independent of US1–US3 (generation path)
- **US5 (Phase 7)**: Depends on Foundational; should complete before v2.0.1 publish (US3 T019)
- **US6 (Phase 8)**: Depends on US3 overrides and existing repro checkpoints
- **US7 (Phase 9)**: Depends on US1 queue and US2 annotations (optional repro from US1)
- **Polish (Phase 10)**: Depends on US3, US5, US6 for full quality pass

### User Story Dependencies

| Story | Depends on | Independent test |
|-------|------------|------------------|
| US1 | Phase 2 | Queue export + tier sort |
| US2 | Phase 2 | Annotate append-only |
| US3 | US2 | Apply overrides + changelog |
| US4 | Phase 2 | Duplicate feedback + diversity report |
| US5 | Phase 2 | Boilerplate validation |
| US6 | US3, repro checkpoints | Selective re-judge summary |
| US7 | US1, US2 | HTML+CSV review pack |

### Parallel Opportunities

- T002, T003 parallel in Setup
- T004–T008 parallel in Foundational (after T004 models land)
- US4 (diversity) and US5 (boilerplate) can proceed in parallel after Phase 2 if staffed separately from US1–US3
- T041 [US7] HTML styling parallel to T040 row builder

---

## Parallel Example: User Story 1

```bash
# Tests + queue core in parallel after Phase 2:
Task T009: tests/unit/test_review_queue.py
Task T010: src/evaluation/generation/review/queue.py  # wait for T009 if TDD

# After T010:
Task T011: CLI export-queue
Task T012: integration test
```

---

## Parallel Example: P2 Stories

```bash
# After Phase 2, split team:
Developer A: US4 (T021–T027) diversity + regenerate-item
Developer B: US5 (T028–T032) boilerplate gate
# Merge before v2.0.1 publish (US3 T019 + US5 gates)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US7)

1. Complete Phase 1–2
2. Complete US1 (review queue) + US2 (annotations) + US7 (review pack)
3. **STOP and VALIDATE**: Export tier-1 queue, annotate 5 items, open review pack
4. Operator can begin manual quality review without overrides or publish

### Incremental Delivery

1. Setup + Foundational → review package ready
2. US1 → repro-driven triage (MVP)
3. US2 → capture human judgments
4. US7 → efficient 20-item audit pack
5. US3 → apply fixes in place
6. US5 → block boilerplate comparisons before publish
7. US6 → validate fixes via selective re-judge
8. US4 → improve future generation diversity (can ship after v2.0.1 if needed)
9. Polish → paper-v1.1 lock

### Suggested MVP Scope

**Minimum**: Phase 1–2 + US1 (T001–T012) — reproduction-driven review queue only.

**Recommended MVP for quality pass**: Phase 1–2 + US1 + US2 + US7 + US3 + US5 (through T032) before operator publish of v2.0.1.

---

## Notes

- Total tasks: **48** (T001–T048)
- US1: 4 impl + 1 test | US2: 2 impl + 1 test | US3: 4 impl + 1 test + 1 integration
- US4: 6 impl + 1 test | US5: 4 impl + 1 test | US6: 4 impl + 1 test + 1 integration | US7: 3 impl + 1 test
- v2.0.0 and paper-v1.0 MUST remain immutable throughout (T048)
- Do not use dev_pool re-selection; in-place patch only per clarifications
