---
description: "Task list for reproduction evaluation validity and stratified ablations (015)"
---

# Tasks: Reproduction Evaluation Validity & Stratified Ablations

**Input**: Design documents from `specs/015-repro-eval-validity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **011–014** merged on `main`; P0 scoring fixes on `main`; branch `015-repro-eval-validity`

**Tests**: Unit and integration tests per plan testing strategy (stratum, structural, judge resume, aggregated notes, stratum export) and success criteria SC-001–SC-007 (SC-002, SC-006 have dedicated validation tasks).

**Organization**: P0 verify → foundational shared modules → **US1 re-judge (MVP) → US2 structural audit → US3 investigation UX → US4 stratified export**; polish adds docs and regression sweep. US3 extends `report_render.py`; US4 extends `export.py` and report loader — implement in story order to reduce merge conflicts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- Extend: `src/evaluation/reproduction/{stratum,structural_extract,export,judge_batch,runner,report_models,report_loader,report_render}.py`
- Extend: `src/cli/commands/repro.py`, `src/evaluation/judges/outcome_scoring.py` (verify only)
- Extend: `templates/reproduction_report.html`, `releases/paper-v1.0/manifest.yaml`
- Tests: `tests/unit/`, `tests/integration/`
- Docs: `docs/research-reproduction.md`, `specs/015-repro-eval-validity/quickstart.md`

---

## Phase 1: Setup (P0 Verification)

**Purpose**: Confirm P0 scoring fixes are present; no re-implementation of FR-000

- [ ] T001 Rebase or merge `015-repro-eval-validity` onto `main` so P0 modules are present: `src/evaluation/judges/outcome_scoring.py`, `src/tracing/trajectory_export.py` (`normalize_trajectory_state`), `src/evaluation/reproduction/export.py` (`load_item_contexts`)
- [ ] T002 [P] Run and pass existing P0 tests: `tests/unit/test_outcome_scoring.py`, `tests/unit/test_trajectory_state_normalize.py`, export-tables tests in `tests/unit/test_paper_table_export.py`

**Checkpoint**: `uv run pytest tests/unit/test_outcome_scoring.py tests/unit/test_trajectory_state_normalize.py -q` passes on feature branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared stratum assignment and structural extraction helpers — MUST complete before US2 and US4

**⚠️ CRITICAL**: Blocks **US2 and US4 only** — US1 and US3 may start after Phase 1 (Setup)

- [ ] T003 Implement `classify_chunk_id`, `assign_primary_evidence_source(relevant_chunk_ids)` in `src/evaluation/reproduction/stratum.py` per `data-model.md` and `research.md` R1
- [ ] T004 [P] Add unit tests `tests/unit/test_stratum.py` covering html-only, xbrl-only, mixed, unknown, legacy `sec-*` ids (no marker → html), and explicit `-html-`/`xbrl` patterns per spec clarifications
- [ ] T005 Implement `extract_used_accessions` and `extract_visited_paths` from normalized `trajectory_snapshot` in `src/evaluation/reproduction/structural_extract.py` per `contracts/structural-metrics.md`
- [ ] T006 [P] Add unit tests `tests/unit/test_structural_extract.py` for accession parsing from `doc-{accession}-...` ids and graph_traversal path extraction

**Checkpoint**: `uv run pytest tests/unit/test_stratum.py tests/unit/test_structural_extract.py -q` passes

---

## Phase 3: User Story 1 - Trustworthy Headline Scores After Re-Judge (Priority: P1) 🎯 MVP

**Goal**: Idempotent re-judge workflow on existing checkpoints; documented operator path; SC-001 strict outcome ordering after re-score

**Independent Test**: Re-score `reports/repro-paper-v1.0` (or fixture), re-export tables; `graph-full` outcome_accuracy strictly exceeds both abstaining ablations; ranking metrics still favor graph-full over flat-chunk

### Tests for User Story 1

- [ ] T007 [P] [US1] Add unit tests `tests/unit/test_judge_batch_resume.py` for v2 resume skip (hydrated evidence), citation-fallback pending, and `--force-rescore` bypass per `contracts/re-judge-workflow.md`
- [ ] T008 [P] [US1] Add integration test `tests/integration/test_rejudge_headline_ordering.py` asserting SC-001 ordering from fixture or mocked re-scored `headline.csv` rows
- [ ] T037 [P] [US1] Add integration test `tests/integration/test_rejudge_evidence_hydration.py` asserting SC-002: ≥80% of graph-full items with `citation_count > 0` have non-empty `evidence_chunks` after `normalize_trajectory_state` on fixture or `reports/repro-paper-v1.0` checkpoint

### Implementation for User Story 1

- [ ] T009 [US1] Extend `_pending_results` in `src/evaluation/reproduction/judge_batch.py` with judge version ≥ v2 + non-empty `evidence_chunks` resume skip per `research.md` R2 and `contracts/re-judge-workflow.md`
- [ ] T010 [US1] Add `--force-rescore` flag to `repro judge-batch` in `src/cli/commands/repro.py` and plumb to `judge_batch.py`
- [ ] T011 [US1] Document re-judge workflow (`judge-batch` → `export-tables` → `report`) in `docs/research-reproduction.md` per `contracts/re-judge-workflow.md` and FR-001
- [ ] T012 [P] [US1] Align `specs/015-repro-eval-validity/quickstart.md` CLI examples with actual `repro.py` flag names after T010

**Checkpoint**: `uv run agent-query repro judge-batch --help` shows `--force-rescore`; resume + SC-001/SC-002 tests pass; docs describe full re-score path

---

## Phase 4: User Story 2 - Graph Agent Quality and Structural Audit (Priority: P1)

**Goal**: Populate `repro_run.json` structural metrics for all five variants; enforce trajectory↔citation consistency on write

**Independent Test**: Smoke run across **all five standard variants** (≥10 binding-heavy items); each variant's `variant_runs[].structural_metrics` non-zero where `expected_bindings` exist; stored trajectory evidence matches answer citations

### Tests for User Story 2

- [ ] T013 [P] [US2] Add unit tests `tests/unit/test_structural_runner.py` for `aggregate_structural_metrics` wiring across all five variants with mocked variant results per `contracts/structural-metrics.md`, FR-005, and SC-003
- [ ] T014 [P] [US2] Add unit tests `tests/unit/test_trajectory_citation_consistency.py` for consistency guard on `BenchmarkResult` write paths per FR-007

### Implementation for User Story 2

- [ ] T015 [US2] Wire `aggregate_structural_metrics` into variant finalization in `src/evaluation/reproduction/runner.py` for all five standard variants; persist on `EvalRunRef.structural_metrics` per FR-005 and `contracts/structural-metrics.md`
- [ ] T016 [US2] Add trajectory↔citation consistency check before atomic `results.json` write in `src/evaluation/reproduction/runner.py` per FR-007 (hydrate evidence from citations when snapshot empty)
- [ ] T017 [US2] Add optional ungrounded-numeric warning when answer tokens are absent from cited chunk text in `src/evaluation/reproduction/runner.py` per `research.md` R8 and FR-006 (warn artifact, non-blocking)

**Checkpoint**: Smoke `repro_run.json` shows non-zero `structural_metrics` for **each of the five variants** when binding-heavy items exist; structural and consistency tests pass

---

## Phase 5: User Story 3 - Readable Investigation Notes (Priority: P2)

**Goal**: ≤25 aggregated investigation notes; expected ablation patterns as single summaries; expandable examples

**Independent Test**: Generate report from full five-variant output; investigation section has bounded aggregated notes with counts; no-walker/xbrl-only zero-citation pattern appears once per variant

### Tests for User Story 3

- [ ] T018 [P] [US3] Add unit tests `tests/unit/test_repro_report_aggregated_notes.py` for pattern aggregation, FR-010 outcome-exceeds guard, 25-note cap, and example item id limit per `data-model.md`

### Implementation for User Story 3

- [ ] T019 [P] [US3] Add `AggregatedInvestigationNote` model in `src/evaluation/reproduction/report_models.py` per `data-model.md`
- [ ] T020 [US3] Implement `aggregate_investigation_notes(bundle)` in `src/evaluation/reproduction/report_render.py`; refactor `detect_run_anomalies` to use aggregation per FR-008–FR-011 and `research.md` R4–R5
- [ ] T021 [US3] Update `_render_anomalies_html()` for expandable notes with up to five `example_item_ids` and drill-down anchor links in `src/evaluation/reproduction/report_render.py`
- [ ] T022 [US3] Add aggregation expand/collapse styles and item anchor hooks in `templates/reproduction_report.html` per SC-004

**Checkpoint**: Report from paper-v1.0 fixture renders ≤25 investigation notes; ablation patterns aggregated

---

## Phase 6: User Story 4 - Stratified Ablation Tables (Priority: P3)

**Goal**: Export and render HTML/XBRL/mixed stratum tables with abstention rate; manifest ablation guidance

**Independent Test**: Export stratified tables from completed repro; HTML stratum shows high no-walker abstention; `variant_delta.csv` unchanged; new stratum CSVs present

### Tests for User Story 4

- [ ] T023 [P] [US4] Add unit tests `tests/unit/test_stratum_export.py` for `by_evidence_source.csv` columns, abstention_rate computation, unknown exclusion, and low-n `na_reason` per `contracts/stratum-export.md`
- [ ] T024 [P] [US4] Add integration test `tests/integration/test_stratum_export_smoke.py` asserting SC-005 (five variants × html/xbrl/mixed strata) from fixture bundle
- [ ] T038 [P] [US4] Extend `tests/integration/test_stratum_export_smoke.py` (or add `test_stratum_sc006_thresholds.py`) asserting SC-006 on HTML stratum: `ablation-no-walker` abstention_rate ≥ 0.80, `graph-full` mrr ≥ 0.10, `ablation-no-walker` mrr ≤ 0.05 per `contracts/stratum-export.md`

### Implementation for User Story 4

- [ ] T025 [US4] Add `StratumTableRow` and `StratumDeltaRow` types and export bundle fields in `src/evaluation/reproduction/export.py` per `data-model.md`
- [ ] T026 [US4] Implement `by_evidence_source.csv` generation with abstention_rate rows in `src/evaluation/reproduction/export.py` per FR-013 and `contracts/stratum-export.md`
- [ ] T027 [US4] Implement `variant_delta_by_source.csv` generation (pooled `variant_delta.csv` unchanged) in `src/evaluation/reproduction/export.py` per FR-014
- [ ] T028 [US4] Record `stratum_audit.unknown_excluded` count in `export_manifest.json` from `src/evaluation/reproduction/export.py`
- [ ] T029 [P] [US4] Extend `PaperTableId`, `CSV_HEADERS`, and `PAPER_TABLE_IDS` in `src/evaluation/reproduction/report_models.py` for `by_evidence_source` and `variant_delta_by_source`
- [ ] T030 [US4] Load optional stratum CSVs in `src/evaluation/reproduction/report_loader.py` with non-fatal warnings for pre-P3 checkpoints
- [ ] T031 [US4] Implement stratified ablation HTML section (variant×metric per stratum, item counts, abstention rate) in `src/evaluation/reproduction/report_render.py` per FR-015
- [ ] T032 [US4] Add `ablation_guidance` per stratum to `releases/paper-v1.0/manifest.yaml` including `ranking_margin` thresholds for SC-006 (`graph_full_mrr_min: 0.10`, `ablation_no_walker_mrr_max: 0.05`, `ablation_no_walker_abstention_rate_min: 0.80`) per FR-016 and `contracts/stratum-export.md`
- [ ] T033 [US4] Extend `repro report --table` filter values for `by_evidence_source` and `variant_delta_by_source` in `src/cli/commands/repro.py`

**Checkpoint**: `tables/by_evidence_source.csv` and `tables/variant_delta_by_source.csv` written on export; report shows stratified section; integration test passes

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, quickstart validation, regression sweep

- [ ] T034 [P] Update `docs/research-reproduction.md` with stratified table catalog, investigation aggregation, and structural metrics pointers
- [ ] T035 Run `specs/015-repro-eval-validity/quickstart.md` validation (re-judge → export → report) on `reports/repro-paper-smoke` or committed fixture
- [ ] T036 [P] Run full feature pytest sweep: `tests/unit/test_stratum*.py`, `tests/unit/test_structural*.py`, `tests/unit/test_judge_batch_resume.py`, `tests/unit/test_repro_report_aggregated_notes.py`, `tests/integration/test_stratum_export_smoke.py`, `tests/integration/test_rejudge_headline_ordering.py`, `tests/integration/test_rejudge_evidence_hydration.py`

**Checkpoint**: All 015 tests green; quickstart steps verified

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS US2 and US4** (US1 can start after Setup if stratum not needed)
- **US1 (Phase 3)**: Depends on Setup; independent of US2–US4 for core re-judge path
- **US2 (Phase 4)**: Depends on Foundational (T005–T006) + Setup
- **US3 (Phase 5)**: Depends on Setup; benefits from US1 re-exported tables but testable with fixtures
- **US4 (Phase 6)**: Depends on Foundational (T003–T004) + US1 export path recommended
- **Polish (Phase 7)**: Depends on desired user stories complete

### User Story Dependencies

```text
Setup (P0 verify)
    ├── Foundational (stratum + structural_extract)
    │       ├── US2 (structural wiring)
    │       └── US4 (stratum export + report)
    ├── US1 (re-judge MVP) ──► US4 (needs re-exported headline data)
    └── US3 (report aggregation) — independent of US2/US4; uses 014 report stack
```

- **US1**: MVP after Setup; no hard dependency on US2/US3/US4
- **US2**: Requires Foundational; parallel with US1 after Foundational if staffed
- **US3**: Can start after Setup; no export changes required
- **US4**: Requires Foundational; best after US1 for end-to-end validation

### Within Each User Story

- Tests before or in parallel with implementation (write failing tests first where practical)
- Models/types before services/export/render logic
- `export.py` before `report_loader.py` before `report_render.py` for US4

### Parallel Opportunities

- T002 ∥ T001 (after rebase)
- T004 ∥ T006 (after T003/T005 respectively)
- T007 ∥ T008 ∥ T037 (US1 tests)
- T013 ∥ T014 (US2 tests)
- T019 ∥ T018 (US3 model vs tests)
- T023 ∥ T024 ∥ T038 (US4 tests)
- T029 ∥ T026–T028 (report models vs export impl after T025)
- US1 and US3 can proceed in parallel after Setup
- US2 and US4 export work can parallelize after Foundational

---

## Parallel Example: User Story 1

```bash
# Tests in parallel:
# T007 tests/unit/test_judge_batch_resume.py
# T008 tests/integration/test_rejudge_headline_ordering.py
# T037 tests/integration/test_rejudge_evidence_hydration.py

# After T009–T010 land:
uv run pytest tests/unit/test_judge_batch_resume.py tests/integration/test_rejudge_headline_ordering.py tests/integration/test_rejudge_evidence_hydration.py -q
```

---

## Parallel Example: User Story 4

```bash
# Tests in parallel:
# T023 tests/unit/test_stratum_export.py
# T024 tests/integration/test_stratum_export_smoke.py
# T038 SC-006 threshold assertions (may extend T024 file)

# Export + report models in parallel after T025:
# T026–T028 export.py
# T029 report_models.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (P0 verify)
2. Complete Phase 3: User Story 1 (re-judge + docs)
3. **STOP and VALIDATE**: Re-score paper-v1.0 or fixture; confirm SC-001 ordering and SC-002 evidence hydration (T037)
4. Ship operator workflow before structural/stratum work

### Incremental Delivery

1. Setup → US1 → validate SC-001 (MVP)
2. Foundational → US2 → validate SC-003 structural metrics on smoke
3. US3 → validate SC-004 aggregated notes
4. US4 → validate SC-005/SC-006 stratified tables
5. Polish → quickstart + full pytest sweep

### Parallel Team Strategy

| Developer | Focus |
|-----------|--------|
| A | US1 re-judge + SC-001 integration |
| B | Foundational + US2 structural wiring |
| C | US3 report aggregation (after Setup) |
| D | US4 export (after Foundational) |

---

## Notes

- Do **not** re-implement FR-000 (P0); verify only in Phase 1
- Do **not** change walker or xbrl-only retrieval behavior (out of scope)
- `variant_delta.csv` schema MUST remain unchanged (FR-014)
- `report_render.py` shared across US3/US4 — merge US3 before US4 report section
- Commit after each task or logical group; branch `015-repro-eval-validity`
