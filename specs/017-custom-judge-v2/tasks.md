---
description: "Task list for custom-judge bundle v2.0 and unified task_success (017)"
---

# Tasks: Custom-Judge Bundle v2.0 and Unified Task Success

**Input**: Design documents from `specs/017-custom-judge-v2/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **011–016** merged; branch `017-custom-judge-v2`

**Tests**: Unit and integration tests per plan testing strategy and success criteria SC-001–SC-008.

**Organization**: Setup → foundational v2 schema/gates → **US1 task_success export (MVP) → US2 answer-GT validation → US3 comparison_structured generation → US5 feasibility/macro gates → US4 net-new publish + paper-v2.0 lock → US6 report semantics**; polish adds docs and acceptance validation. US1/US6 are testable with fixtures before live v2.0 corpus generation; US4 full repro is operator-run after publish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/evaluation/generation/{bundle,item_validator,gemini_item_generator}.py`
- New: `src/evaluation/generation/{feasibility_macro,publish_audit}.py`
- Extend: `src/evaluation/reproduction/{export,report_models,report_render,report_loader}.py`
- Extend: `src/models/{benchmark_generation,evaluation}.py`
- Extend: `src/cli/commands/benchmark_dataset.py`
- New: `configs/benchmarks/custom_judge_v2.yaml`, `releases/paper-v2.0/manifest.yaml`
- Tests: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup

**Purpose**: Confirm branch baseline and v2 design contracts

- [X] T001 Confirm branch `017-custom-judge-v2` is rebased on `main` with 016 outcome scoring and `task_success` export present (`src/evaluation/reproduction/export.py`)
- [X] T002 [P] Review normative contracts in `specs/017-custom-judge-v2/contracts/` against current `src/evaluation/generation/bundle.py` and `src/evaluation/reproduction/export.py`
- [X] T003 [P] Add `configs/benchmarks/custom_judge_v2.yaml` skeleton per `specs/017-custom-judge-v2/contracts/generation-v2-cli.md` (new seed, fiscal window, `multi_filing_min: 40`)

**Checkpoint**: `uv run pytest tests/unit/test_bundle_feasibility_gates.py tests/unit/test_paper_table_export.py -q` passes on feature branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: v2.0 schema, bundle version detection, and shared models — MUST complete before user story phases

**⚠️ CRITICAL**: Blocks all user stories

- [X] T004 Add `AnswerType` enum and required `answer_type` on `GeneratedBenchmarkItem` in `src/models/benchmark_generation.py` per `specs/017-custom-judge-v2/data-model.md`
- [X] T005 [P] Add optional `answer_type` on `GroundTruth` in `src/models/evaluation.py` per `data-model.md`
- [X] T006 [P] Add `PublishAuditRecord` model and `schema_version: "2.0.0"` manifest fields in `src/models/benchmark_generation.py`
- [X] T007 [P] Add `is_v2_bundle(manifest)` / semver helper in `src/evaluation/generation/bundle.py` for v2 gate routing
- [X] T008 Disable rubric-only routing when `is_v2_bundle` in `src/evaluation/generation/bundle.py` (`is_rubric_only_routing` returns False for v2)

**Checkpoint**: `uv run python -c "from models.benchmark_generation import AnswerType; print(AnswerType.COMPARISON_STRUCTURED)"` succeeds

---

## Phase 3: User Story 1 - Unified Headline Success (Priority: P1) 🎯 MVP

**Goal**: paper-v2.0 `task_success` = mean value_alignment over n=200; missing VA = 0; no claim_presence bridge

**Independent Test**: Export fixture repro dir pinned to bundle v2.0.0; headline `task_success` item_count=200 equals mean VA; rubric_alignment row absent (`specs/017-custom-judge-v2/contracts/task-success-v2.md`)

### Tests for User Story 1

- [X] T009 [P] [US1] Add unit tests `tests/unit/test_task_success_v2_export.py` per `contracts/task-success-v2.md`: n=200 denominator, VA-only scores, zero when VA missing, v1.x backward compat

### Implementation for User Story 1

- [X] T010 [US1] Update `_task_success_score` in `src/evaluation/reproduction/export.py` to return `outcome_score` (VA) for all eligible items when release/bundle version ≥ 2.0.0 per FR-009
- [X] T011 [US1] Update `_aggregate_metrics` in `src/evaluation/reproduction/export.py` to set `rubric_alignment` to None and exclude from headline row list for v2 bundles per FR-012
- [X] T012 [P] [US1] Add `bundle_version` / release-tag detection helper in `src/evaluation/reproduction/export.py` reading `releases/paper-v2.0/manifest.yaml` or repro metadata

**Checkpoint**: `uv run pytest tests/unit/test_task_success_v2_export.py -q` passes; fixture export shows task_success n=200

---

## Phase 4: User Story 2 - Answer-GT Coverage on Every Item (Priority: P1)

**Goal**: 100% non-empty `ground_truth.answer`; required_claims on non-numeric types; publish blocked otherwise

**Independent Test**: Validate v2 fixture items; zero null answers; narrative/comparison items have 2–8 claims (`specs/017-custom-judge-v2/spec.md` US2)

### Tests for User Story 2

- [X] T013 [P] [US2] Add unit tests `tests/unit/test_bundle_v2_gates.py` for `missing_answer_gt`, `required_claims`, and `rubric_only_count` gates per `contracts/bundle-v2.0.md`

### Implementation for User Story 2

- [X] T014 [US2] Extend `src/evaluation/generation/item_validator.py` to reject empty `ground_truth.answer` for v2 bundles per FR-002
- [X] T015 [US2] Validate `answer_type` vs `required_claims` rules (numeric/short_label omit; narrative/comparison require claims) in `src/evaluation/generation/item_validator.py` per FR-003
- [X] T016 [US2] Extend `validate_bundle_feasibility` in `src/evaluation/generation/bundle.py` with v2 `answer_gt_coverage` and `rubric_only_count: 0` per `contracts/bundle-v2.0.md`
- [X] T017 [P] [US2] Extend `check_publish_gates` in `src/evaluation/generation/bundle.py` to invoke v2 feasibility branch when `is_v2_bundle`

**Checkpoint**: `uv run pytest tests/unit/test_bundle_v2_gates.py tests/unit/test_item_validator.py -q` passes; draft with null answer fails publish

---

## Phase 5: User Story 3 - Comparison-Structured Ground Truth (Priority: P1)

**Goal**: Multi-filing items use `comparison_structured` answers with per-filing and cross-filing claims

**Independent Test**: Sample comparison items from v2 fixture; ≥2 accessions, canonical both-filings answer, ≥3 claims (`contracts/comparison-gt-template.md`)

### Tests for User Story 3

- [X] T018 [P] [US3] Add unit tests `tests/unit/test_comparison_gt_template.py` for template validation and claim derivation per `contracts/comparison-gt-template.md`

### Implementation for User Story 3

- [X] T019 [US3] Add v2 comparison_structured prompt blocks to `configs/benchmarks/inspiration_profiles/finagentbench.yaml` per `contracts/comparison-gt-template.md`
- [X] T020 [P] [US3] Extend `src/evaluation/generation/gemini_item_generator.py` to emit mandatory `ground_truth.answer`, `answer_type`, and derived `required_claims` for v2 profiles
- [X] T021 [US3] Validate comparison items require `answer_type: comparison_structured`, ≥2 accessions, ≥3 claims in `src/evaluation/generation/item_validator.py` per FR-004

**Checkpoint**: `uv run pytest tests/unit/test_comparison_gt_template.py -q` passes; generated comparison fixture item passes validator

---

## Phase 6: User Story 5 - Feasibility and Scorability Gates (Priority: P2)

**Goal**: Macro-bindability blocking for all 200 items; ≥40 multi-filing items; feasibility + scorability reports

**Independent Test**: Draft with intentional macro failure blocked; draft with <40 multi-filing items blocked (`specs/017-custom-judge-v2/spec.md` US5)

### Implementation for User Story 5

- [X] T022 [P] [US5] Implement `src/evaluation/generation/feasibility_macro.py` calling `validate_macro_binding` per item against bundled snapshot per `research.md` R4
- [X] T023 [US5] Wire `macro_bindability` gate into `validate_bundle_feasibility` in `src/evaluation/generation/bundle.py` for v2 bundles per FR-010
- [X] T024 [US5] Add `multi_filing_floor` gate (≥40 items) to `check_publish_gates` in `src/evaluation/generation/bundle.py` per FR-013
- [X] T025 [P] [US5] Emit `scorability_report.json` on draft completion in `src/evaluation/generation/bundle.py` per `data-model.md`

**Checkpoint**: Macro failure fixture blocks publish; scorability report shows `rubric_only_count: 0`

---

## Phase 7: User Story 4 - Net-New Bundle and paper-v2.0 Lock (Priority: P2)

**Goal**: Greenfield v2.0.0 publish with operator audit; paper-v2.0 manifest; full repro policy (no selective skip)

**Independent Test**: Publish v2.0.0 draft with sign-off; manifest hashes distinct from paper-v1.0; v1.2.0 unchanged (`contracts/paper-v2-release.md`)

### Tests for User Story 4

- [X] T026 [P] [US4] Add integration smoke `tests/integration/test_v2_publish_smoke.py` for publish gate blocking and sign-off requirement

### Implementation for User Story 4

- [X] T027 [US4] Implement `src/evaluation/generation/publish_audit.py` with stratified 20-item sample and sign-off record per FR-011
- [X] T028 [US4] Add `--publish-signoff`, `--operator-id`, and `--bundle-version 2.0.0` to generate/publish in `src/cli/commands/benchmark_dataset.py` per `contracts/generation-v2-cli.md`
- [X] T029 [US4] Create `releases/paper-v2.0/manifest.yaml` per `contracts/paper-v2-release.md` with `full_reproduction_policy.selective_agent_skip: false`
- [X] T030 [P] [US4] Extend `src/cli/commands/repro.py` to resolve `--release paper-v2.0` bundle path from `releases/paper-v2.0/manifest.yaml`
- [X] T031 [US4] Document net-new generation (no `--migrate-from`) and forbid v1.2.0 item reuse in `src/evaluation/generation/bundle.py` publish path per FR-006

**Checkpoint**: Publish with `--publish-signoff` writes `publish_audit.json`; `git diff data/benchmarks/custom-judge/v1.2.0` empty after publish

---

## Phase 8: User Story 6 - Reproduction Reports v2.0 Semantics (Priority: P3)

**Goal**: HTML/CSV reports show task_success as sole headline outcome; omit rubric_alignment for paper-v2.0

**Independent Test**: Generate report from paper-v2.0 fixture; no rubric_alignment row; task_success note documents n=200 VA-only (`specs/017-custom-judge-v2/spec.md` US6)

### Implementation for User Story 6

- [X] T032 [P] [US6] Update `task_success` definition in `METRIC_CATALOG` in `src/evaluation/reproduction/report_models.py` for v2 single-criterion semantics
- [X] T033 [US6] Omit `rubric_alignment` from headline and stratum sections when release is paper-v2.0 in `src/evaluation/reproduction/report_render.py` per FR-012
- [X] T034 [P] [US6] Add paper-v2.0 release detection and metric notes in `src/evaluation/reproduction/report_loader.py`

**Checkpoint**: Fixture report HTML contains task_success n=200 note and no rubric_alignment headline row

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, acceptance validation, immutability checks

- [X] T035 [P] Update `docs/custom-judge-dataset-generation.md` with v2.0 net-new workflow and paper-v2.0 pointers
- [X] T036 [P] Add operator checklist `specs/017-custom-judge-v2/checklists/v2.0-publish.md` mirroring quickstart Phases 1–6
- [X] T037 Run quickstart validation steps in `specs/017-custom-judge-v2/quickstart.md` (fixture or dry-run) and record SC-001–SC-008 status
- [X] T038 Verify ranking metrics unchanged: extend `tests/unit/test_paper_table_export.py` asserting MRR/nDCG definitions identical for v1 vs v2 export paths

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP** (fixture-testable without live corpus)
- **US2 (Phase 4)**: Depends on Foundational — blocks US4 publish
- **US3 (Phase 5)**: Depends on Foundational + US2 validator hooks
- **US5 (Phase 6)**: Depends on US2 v2 feasibility branch
- **US4 (Phase 7)**: Depends on US2, US3, US5 gates complete
- **US6 (Phase 8)**: Depends on US1 export semantics (can parallelize report work after T010)
- **Polish (Phase 9)**: Depends on US1–US6 for full acceptance

### User Story Dependencies

| Story | Depends on | Independent test via |
|-------|------------|----------------------|
| US1 | Foundational | Fixture export + unit tests |
| US2 | Foundational | Validator + gate unit tests |
| US3 | US2 | Comparison fixture + generator tests |
| US5 | US2 | Macro gate fixture |
| US4 | US2, US3, US5 | Publish smoke test |
| US6 | US1 | Report fixture |

### Parallel Opportunities

- **Phase 1**: T002 ∥ T003
- **Phase 2**: T005 ∥ T006 ∥ T007 (after T004)
- **Phase 3**: T009 ∥ T012 (T010–T011 sequential)
- **Phase 4**: T013 ∥ T017 (T014–T016 sequential in validator/bundle)
- **Phase 5**: T018 ∥ T020 (T019, T21 after generator)
- **Phase 6**: T022 ∥ T025 (T023–T24 after macro module)
- **Phase 7**: T026 ∥ T030 (T027–T29, T31 publish path)
- **Phase 8**: T032 ∥ T34 (T33 after T32)
- **Phase 9**: T035 ∥ T36 ∥ T38

### Parallel Example: User Story 1

```bash
# Tests + helper in parallel:
uv run pytest tests/unit/test_task_success_v2_export.py -q  # T009
# Then sequentially: T010 → T011; T012 can start after T007
```

### Parallel Example: User Story 3

```bash
# In parallel:
# T018 tests/unit/test_comparison_gt_template.py
# T020 src/evaluation/generation/gemini_item_generator.py
# Then T019 inspiration profile YAML, T021 validator rules
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 task_success v2 export
4. **STOP and VALIDATE**: `test_task_success_v2_export.py` + fixture export
5. Demo headline metric on mock v2 bundle before live generation

### Incremental Delivery

1. Setup + Foundational → schema ready
2. US1 → unified export semantics (MVP)
3. US2 + US3 → scorable item shape + comparison GT
4. US5 → macro and multi-filing gates
5. US4 → publish v2.0.0 + paper-v2.0 lock + operator repro
6. US6 → report alignment
7. Polish → SC acceptance

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. Then:
   - Developer A: US1 + US6 (export/report)
   - Developer B: US2 + US5 (gates/macro)
   - Developer C: US3 + US4 (generation/publish)
3. Integrate at US4 publish checkpoint

---

## Notes

- No `migrate_v1_*` script — net-new pool only (FR-006)
- v1.2.0 and paper-v1.0 must remain immutable throughout
- Full five-variant × 200-item repro is operator-run (Phase 7+ quickstart), not CI-blocking
- Judge v3.1 VA policy reused; no new model endpoint

---

## Task Summary

| Phase | Story | Task IDs | Count |
|-------|-------|----------|-------|
| 1 Setup | — | T001–T003 | 3 |
| 2 Foundational | — | T004–T008 | 5 |
| 3 US1 | P1 MVP | T009–T012 | 4 |
| 4 US2 | P1 | T013–T017 | 5 |
| 5 US3 | P1 | T018–T021 | 4 |
| 6 US5 | P2 | T022–T025 | 4 |
| 7 US4 | P2 | T026–T031 | 6 |
| 8 US6 | P3 | T032–T034 | 3 |
| 9 Polish | — | T035–T038 | 4 |
| **Total** | | **T001–T038** | **38** |

**Suggested MVP scope**: Phases 1–3 (T001–T012) — foundational v2 schema + task_success export on fixtures.

**Format validation**: All 38 tasks use `- [ ]`, sequential Task ID, story labels on user-story phases, and explicit file paths.
