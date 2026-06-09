---
description: "Task list for fair reproduction outcome scoring (016)"
---

# Tasks: Fair Reproduction Outcome Scoring

**Input**: Design documents from `specs/016-fair-outcome-scoring/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **011–015** merged on `main`; branch `016-fair-outcome-scoring`

**Tests**: Unit and integration tests per plan testing strategy and success criteria SC-001–SC-006 (SC-001 is target with escalation, not a hard CI gate).

**Organization**: Setup → foundational shared criteria/schema → **US1 outcome scoring (MVP) → US2 judge v3 resume + variant criteria wiring → US3 rubrics → US4 bundle v1.1.0 → US5 stratified report**; polish adds acceptance validation and docs. US2 wires `criteria_for_item(item, variant_id)` into `gemini_panel.py` before the resume gate so judged criteria match skip predicates; US3 extends rubric text and `required_claims` injection; US4 is largely independent after foundational `is_numeric_answer_gt`; US5 depends on US1 export semantics.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/evaluation/judges/{outcome_scoring,gemini_panel}.py`
- Extend: `src/evaluation/reproduction/{judge_batch,export,report_render,report_loader}.py`
- Extend: `src/evaluation/generation/{bundle,migrate_v1_1_0}.py`
- Extend: `src/models/benchmark_generation.py`, `configs/judges/gemini_2_5_pro.yaml`
- Extend: `templates/reproduction_report.html`, `releases/paper-v1.0/manifest.yaml`
- New bundle: `data/benchmarks/custom-judge/v1.1.0/`
- Tests: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup

**Purpose**: Confirm branch baseline and design contracts before code changes

- [x] T001 Confirm branch `016-fair-outcome-scoring` is rebased on `main` with 015 reproduction stack present (`judge_batch.py`, `export.py`, `report_render.py`, `outcome_scoring.py`)
- [x] T002 [P] Review normative contracts in `specs/016-fair-outcome-scoring/contracts/` (`outcome-scoring.md`, `judge-v3-resume.md`, `variant-judge-criteria.md`, `bundle-v1.1.0.md`) against current `src/evaluation/judges/outcome_scoring.py` and `judge_batch.py`

**Checkpoint**: `uv run pytest tests/unit/test_outcome_scoring.py tests/unit/test_judge_batch_resume.py -q` passes on feature branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared criterion selection, GT schema extensions, and classifiers — MUST complete before US2, US3, and US4

**⚠️ CRITICAL**: Blocks **US2, US3, US4** — **US1** may start in parallel after Phase 1

- [x] T003 Implement `criteria_for_item(item, variant_id)` with graph vs flat-chunk criterion sets in `src/evaluation/judges/outcome_scoring.py` per `contracts/variant-judge-criteria.md` and `research.md` R3
- [x] T004 [P] Implement `is_numeric_answer_gt(answer: str) -> bool` in `src/evaluation/generation/gt_classifier.py` per `data-model.md` and `research.md` R6
- [x] T005 [P] Add `required_claims: list[str] | None` to `GroundTruth` in `src/models/evaluation.py` per `data-model.md`
- [x] T006 [P] Add unit tests `tests/unit/test_variant_criteria.py` for graph-full vs flat-chunk criterion sets and GT-conditional `value_alignment`/`claim_presence` inclusion
- [x] T007 [P] Add unit tests `tests/unit/test_numeric_answer_gt.py` for percentage, currency, short-label, and narrative answer classification

**Checkpoint**: `uv run pytest tests/unit/test_variant_criteria.py tests/unit/test_numeric_answer_gt.py -q` passes

---

## Phase 3: User Story 1 - Trustworthy Outcome Accuracy (Priority: P1) 🎯 MVP

**Goal**: Answer-GT outcome uses `value_alignment` only; missing VA scores zero; ranking metrics unchanged

**Independent Test**: Re-score fixture checkpoints, export tables; `outcome_accuracy` equals mean `value_alignment` on answer-GT items; MRR/nDCG per variant differ < 0.001 from pre-fix baseline (SC-002). Does **not** require graph-full > flat-chunk (that is SC-001, validated in Polish after US4).

### Tests for User Story 1

- [x] T008 [P] [US1] Add unit tests `tests/unit/test_outcome_scoring_fair.py` per `contracts/outcome-scoring.md`: VA-only mapping, zero when VA absent, no synthesis fallback, rubric-GT exclusion unchanged

### Implementation for User Story 1

- [x] T009 [US1] Remove `synthesis_grounding` fallback for answer-GT items in `compute_outcome_scores` in `src/evaluation/judges/outcome_scoring.py` per FR-001 and `research.md` R1
- [x] T010 [US1] Verify rubric-GT alignment uses `claim_presence` only (zero when absent) in `src/evaluation/judges/outcome_scoring.py` per FR-002
- [x] T011 [P] [US1] Add regression test in `tests/unit/test_paper_table_export.py` asserting ranking columns (MRR, MAP, nDCG@10) unchanged when only judge/outcome fields change per FR-012 and SC-002

**Checkpoint**: `uv run pytest tests/unit/test_outcome_scoring_fair.py tests/unit/test_outcome_scoring.py -q` passes; synthesis never used as outcome for answer-GT. SC-001/SC-006 **not** in scope for MVP.

---

## Phase 4: User Story 2 - Complete Judge Coverage on Resume (Priority: P1)

**Goal**: Judge v3 with variant-aware criteria in `gemini_panel` and criterion-completeness resume gate; v2 partial verdicts always re-judged

**Independent Test**: Seed fixture with v2 verdicts missing `value_alignment`; run `judge-batch` without `--force-rescore`; items re-judged to v3 with full variant-appropriate criterion set; complete v3 verdicts skipped

### Tests for User Story 2

- [x] T012 [P] [US2] Add unit tests `tests/unit/test_judge_v3_resume.py` for `should_skip_judging` per `contracts/judge-v3-resume.md` (v2 always pending, v3 complete skips, force-rescore bypasses)
- [x] T013 [P] [US2] Add integration test `tests/integration/test_judge_batch_v2_to_v3.py` seeding v2 partial verdicts and asserting v3 full criteria after batch
- [x] T014 [P] [US2] Update `tests/unit/test_judge_batch_resume.py` for v3 + criterion-completeness expectations (replace v2-only skip assertions)

### Implementation for User Story 2

- [x] T015 [US2] Bump `JUDGE_VERSION` to `"v3"` and persist full `criteria` list on verdicts in `src/evaluation/judges/gemini_panel.py` per `research.md` R2
- [x] T016 [US2] Wire `criteria_for_item(item, variant_id)` for criterion selection in `src/evaluation/judges/gemini_panel.py` per `contracts/variant-judge-criteria.md` and FR-009 (**must complete before T017** so judged criteria match resume skip predicate)
- [x] T017 [US2] Implement `should_skip_judging` using `criteria_for_item` completeness in `src/evaluation/reproduction/judge_batch.py` per `contracts/judge-v3-resume.md` and FR-003
- [x] T018 [US2] Ensure `--force-rescore` bypasses v3 complete skip in `src/evaluation/reproduction/judge_batch.py` per FR-004
- [x] T019 [US2] Reject or retry judge API responses missing required criteria keys before marking item complete in `src/evaluation/judges/gemini_panel.py` per spec edge cases

**Checkpoint**: `uv run pytest tests/unit/test_judge_v3_resume.py tests/integration/test_judge_batch_v2_to_v3.py -q` passes; v2 checkpoints never skip; flat-chunk verdicts use retrieval-focused criteria

---

## Phase 5: User Story 3 - Judge Rubrics That Penalize Chunk-Dump Gaming (Priority: P2)

**Goal**: Anti-gaming rubric text and `required_claims` prompt injection; chunk-dump answers score low on synthesis

**Independent Test**: Mock-judge or fixture tests show chunk-dump answers score synthesis=0; qualitative GT uses claim coverage via `required_claims` prompt injection

### Tests for User Story 3

- [x] T020 [P] [US3] Add unit tests `tests/unit/test_judge_rubric_prompts.py` for anti-chunk-dump synthesis rubric, wrong-filing penalty, and `required_claims` prompt injection in `src/evaluation/judges/gemini_panel.py`

### Implementation for User Story 3

- [x] T021 [P] [US3] Add `answer_quality` criterion and anti-dump `synthesis_grounding` rubric text in `configs/judges/gemini_2_5_pro.yaml` per `research.md` R4 and FR-005
- [x] T022 [P] [US3] Extend `value_alignment` rubric for claim-coverage scoring (not header overlap) in `configs/judges/gemini_2_5_pro.yaml` per FR-006
- [x] T023 [US3] Inject `required_claims` into judge prompts in `src/evaluation/judges/gemini_panel.py` when present on item ground truth per `contracts/variant-judge-criteria.md`
- [x] T024 [US3] Assert stored flat-chunk verdicts exclude `trajectory_coherence` and `routing_decisions` in `tests/unit/test_variant_criteria.py` integration with mock judge path

**Checkpoint**: flat-chunk criterion set is retrieval-focused; chunk-dump fixture scores low synthesis in unit tests

---

## Phase 6: User Story 4 - Higher-Quality Benchmark Items (Priority: P2)

**Goal**: Publish immutable bundle `v1.1.0` with required-claims, rubric routing, binding fixes, feasibility gates, and manifest update

**Independent Test**: `check_publish_gates` blocks infeasible comparison items; published `v1.1.0` has zero feasibility failures; manifest points to new bundle path (SC-006)

### Tests for User Story 4

- [x] T025 [P] [US4] Add unit tests `tests/unit/test_bundle_feasibility_gates.py` for comparison partner and reference-corpus gates in `src/evaluation/generation/bundle.py` per `research.md` R8

### Implementation for User Story 4

- [x] T026 [US4] Implement `src/evaluation/generation/migrate_v1_1_0.py` to build draft from `v1.0.0` with `CHANGELOG.md` per `contracts/bundle-v1.1.0.md`
- [x] T027 [US4] Apply rubric-only routing for comparison/multi-hop/reference question types in `src/evaluation/generation/migrate_v1_1_0.py` per `research.md` R7 and FR-007
- [x] T028 [US4] Attach `required_claims` to non-numeric answer-GT items in `src/evaluation/generation/migrate_v1_1_0.py` per FR-007 and `research.md` R6
- [x] T029 [US4] Repair infeasible `expected_bindings` (missing comparison partners, unreachable reference filings) in `src/evaluation/generation/migrate_v1_1_0.py` with per-item `CHANGELOG.md` entries (`change_types: bindings`) per `contracts/bundle-v1.1.0.md` migration category 3
- [x] T030 [US4] Extend `check_publish_gates` in `src/evaluation/generation/bundle.py` for binding feasibility and required-claims validation per FR-008
- [x] T031 [US4] Publish `data/benchmarks/custom-judge/v1.1.0/` with `manifest.json`, `items.jsonl`, `CHANGELOG.md`, and `feasibility_report.json`
- [x] T032 [US4] Update `custom_judge_version` and `custom_judge_bundle_path` in `releases/paper-v1.0/manifest.yaml` per FR-013
- [x] T033 [P] [US4] Document selective re-run (re-judge unchanged items; agent re-run for changelog items) in `specs/016-fair-outcome-scoring/quickstart.md` per FR-014 and `research.md` R9

**Checkpoint**: `v1.1.0` publish gates pass with zero infeasible comparison items; manifest references `1.1.0`

---

## Phase 7: User Story 5 - Interpretable Stratified Reporting (Priority: P3)

**Goal**: Prominent outcome-by-profile and outcome-by-stratum report sections; SC-001 escalation note; export metadata records v3 policy

**Independent Test**: Generate report from five-variant fixture; profile and stratum outcome sections appear above pooled headline; `OUTCOME_ORDERING_REGRESSION` emitted when graph-full ≤ flat-chunk on HTML stratum

### Tests for User Story 5

- [x] T034 [P] [US5] Add unit tests `tests/unit/test_outcome_report_sections.py` for profile/stratum section rendering and `OUTCOME_ORDERING_REGRESSION` note in `src/evaluation/reproduction/report_render.py`

### Implementation for User Story 5

- [x] T035 [P] [US5] Promote outcome-by-profile table section in `src/evaluation/reproduction/report_render.py` and `templates/reproduction_report.html` per FR-010
- [x] T036 [P] [US5] Promote outcome-by-evidence-source (stratum) table section in `src/evaluation/reproduction/report_render.py` and `templates/reproduction_report.html` per FR-010
- [x] T037 [US5] Implement `OUTCOME_ORDERING_REGRESSION` and `INCOMPLETE_JUDGE_CRITERIA` patterns in `aggregate_investigation_notes` in `src/evaluation/reproduction/report_render.py` per FR-011 and `research.md` R10
- [x] T038 [US5] Ensure `src/evaluation/reproduction/report_loader.py` loads `by_profile` and `by_evidence_source` outcome tables into `ReproOutputBundle` for stratified report sections per FR-010 and `plan.md`
- [x] T039 [US5] Record `min_judge_version`, `custom_judge_version`, and `outcome_scoring_policy` in export manifest metadata in `src/evaluation/reproduction/export.py` per `data-model.md`
- [x] T040 [US5] Extend `tests/unit/test_repro_report_aggregated_notes.py` to assert `RUBRIC_ALIGNMENT_ZERO` absent after v3 complete fixture per SC-003

**Checkpoint**: HTML report shows stratified outcome sections; investigation notes include SC-001 regression when applicable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Acceptance validation, operator docs, and regression sweep

- [ ] T041 Run operator workflow in `specs/016-fair-outcome-scoring/quickstart.md` against `reports/repro-paper-v1.0` with manifest on bundle v1.1.0 (judge-batch → export-tables → report); record SC-001 outcome (pass or `OUTCOME_ORDERING_REGRESSION` note) — **deferred**: run after full implementation verified locally
- [x] T042 [P] Add integration test `tests/integration/test_fair_outcome_ranking_unchanged.py` asserting SC-002 ranking metric delta < 0.001 on fixed checkpoints
- [x] T043 [P] Add integration assertion for SC-004 (<5% answer-GT missing `value_alignment` after v3 re-score) in `tests/integration/test_judge_batch_v2_to_v3.py` or dedicated fixture test
- [x] T044 [P] Add integration or documented checklist for SC-005 synthesis-fallback inversion pair count decrease on HTML answer-GT items (baseline: `reports/repro-paper-v1.0` pre-fix checkpoints)
- [x] T045 Update `docs/research-reproduction.md` with v3 re-judge path, v1.1.0 bundle migration, and selective re-run operator guidance
- [x] T046 Final regression: `uv run pytest tests/unit tests/contract tests/integration -m "not slow" -q` (016-focused subset: 55 tests green; full suite requires live LLM fixtures)

**Checkpoint**: quickstart workflow completes; CI lint + test suite green; SC-001 and SC-006 validated here (not in MVP Phases 1–4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — blocks US2, US3, US4
- **US1 (Phase 3)**: Can start after Setup (parallel with Phase 2)
- **US2 (Phase 4)**: Depends on Phase 2 (`criteria_for_item`); **T016 before T017** (gemini criteria before resume gate)
- **US3 (Phase 5)**: Depends on US2 T016 (variant criteria wired); rubric YAML can parallel T021/T022
- **US4 (Phase 6)**: Depends on Phase 2 (`is_numeric_answer_gt`, `required_claims` model) — parallel with US3 after Phase 2
- **US5 (Phase 7)**: Depends on US1 outcome semantics; best after US2/US3 for meaningful rubric alignment; T038 before T035/T036 render
- **Polish (Phase 8)**: Depends on US4 for SC-001/SC-006; depends on US5 for regression note UX

### User Story Dependencies

```text
Phase 2 (Foundational)
    ├── US1 (outcome scoring) — parallel
    ├── US2 (v3 resume) — needs T003; T016 before T017
    ├── US3 (rubrics) — needs US2 T016
    └── US4 (bundle) — needs T004, T005

US1 ──► US5 (export/report semantics)
US2 + US3 ──► US5 (rubric alignment notes)
US4 ──► Polish SC-001 / SC-006 acceptance
```

### Parallel Opportunities

- **Phase 1**: T002 parallel with T001
- **Phase 2**: T004, T005, T006, T007 parallel after T003 starts
- **US1 + Phase 2**: US1 tests (T008) can run while Phase 2 completes
- **US2 tests**: T012, T013, T014 parallel; then T015 → T016 → T017–T019 sequential
- **US3 config**: T021, T022 parallel; T020 parallel with T021
- **US4**: T025 parallel with T026; T029 after T026; T033 parallel after T031
- **US5**: T034, T035, T036 parallel (after T038)
- **Polish**: T042, T043, T044 parallel

### Parallel Example: User Story 2

```bash
# Tests in parallel:
tests/unit/test_judge_v3_resume.py
tests/integration/test_judge_batch_v2_to_v3.py
tests/unit/test_judge_batch_resume.py

# Implementation order (do not reorder):
# T015 v3 stamp → T016 gemini variant criteria → T017 resume gate → T018/T019
```

### Parallel Example: User Story 4

```bash
# After T026 draft builder exists:
tests/unit/test_bundle_feasibility_gates.py   # T025
migrate_v1_1_0.py rubric routing            # T027
migrate_v1_1_0.py required_claims           # T028
migrate_v1_1_0.py binding repairs           # T029
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. Complete Phase 1–2 (foundational criteria)
2. Complete Phase 3 (US1) — fixes outcome scoring immediately
3. Complete Phase 4 (US2) — v3 re-judge with variant-aware criteria (T016 before resume gate)
4. **STOP and VALIDATE**: Re-score smoke fixture; confirm VA-only outcome (FR-001–002), v3 re-judge (FR-003–004), SC-002 ranking unchanged, SC-004 judge coverage
5. Operator can re-run `judge-batch --force-rescore` on paper-v1.0 before rubric/bundle work lands

**MVP does not validate**: SC-001 (graph-full vs flat-chunk ordering), SC-005 (synthesis inversion pairs), SC-006 (v1.1.0 bundle) — deferred to Phases 6–8.

### Incremental Delivery

1. US1 + US2 → trustworthy re-score on existing bundle (FR-001–004, SC-002, SC-004)
2. US3 → rubric anti-gaming (flat-chunk fairness)
3. US4 → v1.1.0 bundle (dataset quality for paper; SC-006)
4. US5 → report prominence and SC-001 escalation UX
5. Polish → SC-001, SC-005, SC-006 acceptance

### Suggested MVP Scope

**Phases 1–4 (T001–T019)**: Outcome VA-only + judge v3 resume with variant criteria — delivers FR-001–FR-004 and FR-009 wiring without bundle migration or rubric YAML refresh.

---

## Task Summary

| Phase | Story | Tasks | Count |
|-------|-------|-------|-------|
| 1 Setup | — | T001–T002 | 2 |
| 2 Foundational | — | T003–T007 | 5 |
| 3 US1 P1 | US1 | T008–T011 | 4 |
| 4 US2 P1 | US2 | T012–T019 | 8 |
| 5 US3 P2 | US3 | T020–T024 | 5 |
| 6 US4 P2 | US4 | T025–T033 | 9 |
| 7 US5 P3 | US5 | T034–T040 | 7 |
| 8 Polish | — | T041–T046 | 6 |
| **Total** | | **T001–T046** | **46** |

### Independent Test Criteria

| Story | Independent Test |
|-------|------------------|
| US1 | VA-only outcome; zero when missing; ranking unchanged (SC-002 only) |
| US2 | v2 partial → re-judged v3 with variant criteria; v3 complete skipped; SC-004 |
| US3 | Chunk-dump low synthesis; flat-chunk no trajectory criteria |
| US4 | v1.1.0 publish gates pass; binding fixes in CHANGELOG; manifest → 1.1.0 (SC-006) |
| US5 | Profile/stratum outcome sections visible; SC-001 regression note |

---

## Notes

- SC-001 failure does **not** block merge; ship `OUTCOME_ORDERING_REGRESSION` note per clarification; validated in Polish (T041), not MVP
- Do not change ranking metric definitions (FR-012)
- `v1.0.0` bundle remains immutable; all dataset fixes in `v1.1.0`
- Re-score requires `export-tables` before `report` — document in quickstart
- Commit after each phase checkpoint; use `--force-rescore` for first v3 migration on paper-v1.0
- **T016 before T017**: judged criteria must match resume skip predicate (fixes analyze finding I1)
