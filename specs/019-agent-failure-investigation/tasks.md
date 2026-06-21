---
description: "Task list for agent failure investigation and remediation (019)"
---

# Tasks: Agent Failure Investigation and Remediation

**Input**: Design documents from `specs/019-agent-failure-investigation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **014** (repro report), **018** (review queue/annotations) merged; branch `019-agent-failure-investigation`; local `reports/repro-paper-v1.0/` and draft `data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json`

**Tests**: Unit and integration tests per plan testing strategy; failure-mode regression suite required by FR-007 and US4 acceptance scenarios.

**Organization**: Setup → foundational models/loaders → **US2 taxonomy (P1) → US1 investigation pack (P1 MVP) → US5 cohort gate (P1) → US3 cohort debug (P2) → US4 agent remediations + regression (P2) → US6 018 integration (P3)** → polish. US1+US2 deliver investigation MVP; US5 blocks paper-v1.1 repro; US4 must land before cohort gate can pass `require_regression_suite_pass`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/evaluation/reproduction/investigation/{pack,taxonomy,materialization_audit,edgar_links,graph_context,cohort,cohort_debug,cohort_gate}.py`
- New: `src/models/investigation.py`
- Extend: `src/evaluation/reproduction/{report_render.py,report_models.py,runner.py,smoke_gate.py}`
- Extend: `src/evaluation/generation/review/quality_summary.py`
- Extend: `src/retrieval/{synthesis.py,macro/}`
- Extend: `src/cli/commands/{repro.py,benchmark_dataset.py}`
- Extend: `releases/paper-v1.1/manifest.yaml`
- Tests: `tests/unit/`, `tests/integration/`, `tests/regression/failure_modes/`

---

## Phase 1: Setup

**Purpose**: Scaffold investigation package and paper-v1.1 manifest hooks

- [X] T001 Create `src/evaluation/reproduction/investigation/` package with `__init__.py` per `specs/019-agent-failure-investigation/plan.md` structure
- [X] T002 [P] Add all Pydantic models from `specs/019-agent-failure-investigation/data-model.md` in `src/models/investigation.py` (`EngineeringFailureClass`, `FailureInvestigationRow`, `Tier1CohortFile`, `CohortDebugSummary`, `CohortValidationReport`, etc.)
- [X] T003 [P] Add `cohort_gate_thresholds` section stub to `releases/paper-v1.1/manifest.yaml` per `specs/019-agent-failure-investigation/research.md` R9 defaults

**Checkpoint**: `uv run python -c "from models.investigation import FailureInvestigationRow"` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared loaders and report model extensions — MUST complete before user story phases

**⚠️ CRITICAL**: Blocks all user stories

- [X] T004 Implement shared investigation input loader in `src/evaluation/reproduction/investigation/_loaders.py` merging review queue, repro `results.json`, draft bundle items/annotations, and bundle corpus paths
- [X] T005 [P] Extend `src/evaluation/reproduction/report_models.py` with `FailureInvestigationFields` container for drill-down reuse per `specs/019-agent-failure-investigation/contracts/failure-investigation-pack.md`

**Checkpoint**: Loader unit smoke against `reports/repro-paper-v1.0/` + quality-v2.0.1 draft returns typed rows without export

---

## Phase 3: User Story 2 — Auto-Suggested Failure Taxonomy (Priority: P1)

**Goal**: Rule-ordered engineering failure class suggestion with documented default mapping to 018 human classes

**Independent Test**: Run taxonomy on 20 stratified tier-1 items; ≥70% match reviewer primary class (SC-002)

### Tests for User Story 2

- [X] T006 [P] [US2] Create unit tests in `tests/unit/test_failure_taxonomy.py` covering all seven `EngineeringFailureClass` rules and mapping rollups per `specs/019-agent-failure-investigation/contracts/taxonomy-suggestion.md`

### Implementation for User Story 2

- [X] T007 [P] [US2] Implement rule-ordered classifier in `src/evaluation/reproduction/investigation/taxonomy.py` (abstention → binding → template_dump → numeric_xbrl → comparison → retrieval_mismatch → gt_suspected)
- [X] T008 [US2] Add `ENGINEERING_TO_HUMAN_CLASS` default mapping constant and rollup helper in `src/evaluation/reproduction/investigation/taxonomy.py` preserving separate `human_failure_class` from annotations

**Checkpoint**: `uv run pytest tests/unit/test_failure_taxonomy.py -q` passes

---

## Phase 4: User Story 1 — Unified Failure Investigation View (Priority: P1) 🎯 MVP

**Goal**: Static HTML+CSV failure-investigation pack and repro report drill-down with EDGAR links, corpus excerpts, materialization audit, and graph context links

**Independent Test**: Export pack for 10 tier-1 items; reviewer classifies primary failure mode in <5 min/item using only the pack (SC-001)

### Tests for User Story 1

- [X] T009 [P] [US1] Create unit tests in `tests/unit/test_edgar_links.py` for CIK resolution, URL format, and `link_omitted_reason` fallbacks per `specs/019-agent-failure-investigation/contracts/edgar-filing-links.md`
- [X] T010 [P] [US1] Create unit tests in `tests/unit/test_materialization_audit.py` for expected vs visited section paths and `binding_miss` detection
- [X] T011 [US1] Create integration test in `tests/integration/test_failure_investigation_pack.py` exporting 10-item fixture cohort to HTML+CSV with required columns

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement EDGAR link builder in `src/evaluation/reproduction/investigation/edgar_links.py` using bundle manifest `filing_refs` CIK + accession
- [X] T013 [P] [US1] Implement materialization audit builder in `src/evaluation/reproduction/investigation/materialization_audit.py` from benchmark bindings, trajectory snapshot, and citations
- [X] T014 [P] [US1] Implement link-first graph context panel in `src/evaluation/reproduction/investigation/graph_context.py` writing `graph_context/{item_id}.html` with optional inline embed when pre-rendered bundle data exists
- [X] T015 [US1] Implement `build_failure_investigation_rows()` and HTML+CSV export in `src/evaluation/reproduction/investigation/pack.py` calling taxonomy, edgar_links, materialization_audit, and graph_context
- [X] T016 [US1] Wire `benchmark-dataset review export-investigation` command in `src/cli/commands/benchmark_dataset.py` per `specs/019-agent-failure-investigation/contracts/failure-investigation-pack.md`
- [X] T017 [US1] Extend `src/evaluation/reproduction/report_render.py` item drill-down to call shared row builder from `pack.py` (no field drift)
- [X] T018 [US1] Add `--with-investigation` flag to `repro report` in `src/cli/commands/repro.py`

**Checkpoint**: `uv run agent-query benchmark-dataset review export-investigation --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json --repro-input reports/repro-paper-v1.0 --output reports/repro-paper-v1.0/investigation` produces HTML+CSV; repro report drill-down shows same fields

---

## Phase 5: User Story 5 — Pre-Repro Validation Gate (Priority: P1)

**Goal**: Frozen 84-item tier-1 cohort, cohort validation report, hard block on paper-v1.1 `run-all` with audited `--force-cohort-gate` override

**Independent Test**: Run cohort-validate before/after a known fix; gate blocks full repro when thresholds fail and passes when met (US5 acceptance scenarios)

### Tests for User Story 5

- [X] T019 [P] [US5] Create unit tests in `tests/unit/test_cohort_gate.py` for threshold evaluation, baseline comparison deltas, and override audit record schema

### Implementation for User Story 5

- [X] T020 [US5] Implement tier-1 cohort freeze from `review_queue.json` in `src/evaluation/reproduction/investigation/cohort.py` writing `Tier1CohortFile` with provenance hash (~84 ids)
- [X] T021 [US5] Wire `repro cohort-freeze` command in `src/cli/commands/repro.py` per `specs/019-agent-failure-investigation/quickstart.md`
- [X] T022 [US5] Implement cohort validation report builder in `src/evaluation/reproduction/investigation/cohort_gate.py` with tier-1 zero count, strong-retrieval zero count, synthesis_path histogram, and engineering failure distribution
- [X] T023 [US5] Reuse `max_mrr_ok_va_zero` logic from `src/evaluation/reproduction/smoke_gate.py` in cohort validation metrics
- [X] T024 [US5] Wire `repro cohort-validate` command in `src/cli/commands/repro.py` per `specs/019-agent-failure-investigation/contracts/cohort-gate.md`
- [X] T025 [US5] Integrate hard block in `repro run-all` for `releases/paper-v1.1/manifest.yaml` with `--force-cohort-gate` append to `cohort_gate_overrides.jsonl` in `src/cli/commands/repro.py`
- [X] T026 [US5] Finalize `cohort_gate_thresholds` values and `baseline_snapshot_path` in `releases/paper-v1.1/manifest.yaml`

**Checkpoint**: `repro cohort-validate` writes `cohort_validation_report.json`; failed thresholds cause `repro run-all` exit 1 unless force override recorded

---

## Phase 6: User Story 3 — Cohort Debug Observability (Priority: P2)

**Goal**: Re-run (default) or replay cohort items with structured per-item summaries and enriched stdout progress lines

**Independent Test**: Re-run 5-item debug cohort; each item emits summary JSON and stdout line with item id, variant, synthesis path, citation count, outcome, weakest judge criterion

### Tests for User Story 3

- [X] T027 [P] [US3] Add `tests/fixtures/cohort_debug_smoke_ids.json` five-item fixture for smoke runs
- [X] T028 [US3] Create integration test in `tests/integration/test_cohort_debug_smoke.py` for re-run and `--replay` modes

### Implementation for User Story 3

- [X] T029 [US3] Implement cohort debug re-run and replay modes in `src/evaluation/reproduction/investigation/cohort_debug.py` writing `cohort_debug/{item_id}.summary.json` per `specs/019-agent-failure-investigation/contracts/cohort-debug-cli.md`
- [X] T030 [US3] Extend stdout progress lines in `src/evaluation/reproduction/runner.py` with item id, variant, synthesis path, citation count, outcome score, and weakest judge criterion
- [X] T031 [US3] Wire `repro cohort-debug` command in `src/cli/commands/repro.py` with `--trace normal --trace-json` defaults for re-run mode

**Checkpoint**: `uv run pytest tests/integration/test_cohort_debug_smoke.py -q` passes; replay mode completes without agent invocation

---

## Phase 7: User Story 4 — Targeted Agent Remediation with Regression Tests (Priority: P2)

**Goal**: Macro binding, numeric XBRL synthesis, and template-dump guard fixes each registered in failure-mode regression suite

**Independent Test**: Each remediation cluster has a test that fails without the fix and passes with it; full suite green in CI

### Tests for User Story 4

- [X] T032 [P] [US4] Scaffold `tests/regression/failure_modes/` with `conftest.py` and shared fixture loader per `specs/019-agent-failure-investigation/contracts/failure-mode-regression.md`
- [X] T033 [P] [US4] Add M1 macro binding regression fixture and test in `tests/regression/failure_modes/test_macro_binding.py`
- [X] T034 [P] [US4] Add M2 numeric XBRL regression fixture and test in `tests/regression/failure_modes/test_numeric_xbrl_synthesis.py`
- [X] T035 [P] [US4] Add M3 template-dump guard regression fixture and test in `tests/regression/failure_modes/test_template_dump_guard.py`
- [X] T036 [P] [US4] Add M4 comparison narrative regression fixture and test in `tests/regression/failure_modes/test_comparison_narrative.py`
- [X] T037 [US4] Create integration test in `tests/integration/test_failure_mode_regression.py` running full regression directory

### Implementation for User Story 4

- [X] T038 [US4] Implement macro binding fixes (10-K vs 10-Q, fiscal period, entity disambiguation) in `src/retrieval/macro/` for M1 patterns
- [X] T039 [US4] Extend `_try_synthesize_numeric_xbrl` and block template fallback when ranked XBRL evidence exists in `src/retrieval/synthesis.py` for M2/M3
- [X] T040 [US4] Improve comparison narrative synthesis in `src/retrieval/synthesis.py` for M4 cross-filing contrast patterns
- [X] T041 [US4] Wire `require_regression_suite_pass` check in `src/evaluation/reproduction/investigation/cohort_gate.py` invoking `tests/regression/failure_modes/`

**Checkpoint**: `uv run pytest tests/regression/failure_modes -q` passes; cohort gate fails when regression suite fails

---

## Phase 8: User Story 6 — Integration with Dataset Quality Review (Priority: P3)

**Goal**: Extend 018 review CLI and quality summary without replacing existing workflows

**Independent Test**: Export tier-1 queue via existing CLI, generate investigation pack, annotate one item, verify quality summary reflects GT vs agent failure counts separately

### Implementation for User Story 6

- [X] T042 [P] [US6] Extend `src/evaluation/generation/review/quality_summary.py` with `engineering_failure_counts` rollup using taxonomy default mapping
- [X] T043 [US6] Add `cohort_validation_status` field to quality pass summary in `src/evaluation/generation/review/quality_summary.py` from latest `cohort_validation_report.json`
- [X] T044 [US6] Align `export-investigation` CLI flags with `export-sheet` (`--queue-file`, `--repro-input`, `--draft`, `--item-ids-file`) in `src/cli/commands/benchmark_dataset.py`
- [X] T045 [US6] Ensure investigation pack regeneration picks up selective re-judge outcome updates without full agent re-run when only GT/judge scores change

**Checkpoint**: `benchmark-dataset review summary` shows engineering taxonomy counts; `agent_failure` annotations excluded from dataset-caused zero tallies

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quickstart validation, and operator runbook alignment

- [X] T046 [P] Update `docs/research-reproduction.md` with investigation pack, cohort debug, and cohort gate workflow
- [X] T047 [P] Update `docs/eval-dataset-quality.md` with engineering taxonomy mapping and dual-layer annotation guidance
- [X] T048 Run full validation checklist from `specs/019-agent-failure-investigation/quickstart.md` (pack export, cohort freeze, debug smoke, regression suite, cohort validate, run-all gate behavior)
- [X] T049 [P] Verify paper-v1.0 and v2.0.0 artifacts remain immutable; confirm no retroactive baseline checksum changes in `releases/paper-v1.0/expected_checksums.json`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **blocks all user stories**
- **US2 Taxonomy (Phase 3)**: Depends on Phase 2 — blocks US1 pack taxonomy fields
- **US1 Investigation Pack (Phase 4)**: Depends on Phases 2–3 — **MVP deliverable**
- **US5 Cohort Gate (Phase 5)**: Depends on Phase 2; full pass requires US4 regression suite (T041)
- **US3 Cohort Debug (Phase 6)**: Depends on Phase 2; can parallelize with Phase 5 after foundational
- **US4 Remediations (Phase 7)**: Depends on Phase 6 observability for before/after diff; blocks cohort gate pass
- **US6 Integration (Phase 8)**: Depends on US1 pack and US5 cohort artifacts
- **Polish (Phase 9)**: Depends on desired user stories complete

### User Story Dependencies

| Story | Priority | Depends on | Independently testable via |
|-------|----------|------------|----------------------------|
| US2 | P1 | Foundational | `test_failure_taxonomy.py` |
| US1 | P1 | US2 + Foundational | `export-investigation` + pack integration test |
| US5 | P1 | Foundational; US4 for pass | `cohort-validate` + gate unit tests |
| US3 | P2 | Foundational | `cohort-debug` smoke integration test |
| US4 | P2 | US3 (recommended) | `tests/regression/failure_modes/` |
| US6 | P3 | US1, US5 | quality summary + export flag parity |

### Parallel Opportunities

- **Phase 1**: T002 and T003 in parallel
- **Phase 2**: T005 parallel with T004 after T001
- **Phase 3**: T006 parallel with T007; T008 after T007
- **Phase 4**: T009–T014 all parallel before T015; T016–T018 after T015
- **Phase 5**: T019 parallel with T022 prep; T026 after T022–T025
- **Phase 6**: T027 parallel with T029 prep; T030 parallel with T029
- **Phase 7**: T033–T036 all parallel; T038–T040 sequential by cluster; implement after tests fail (TDD for regressions)
- **Phase 8**: T042 parallel with T044 prep
- **Phase 9**: T046, T047, T049 in parallel

### Parallel Example: User Story 1

```bash
# Launch independent US1 modules together:
Task T012: edgar_links.py
Task T013: materialization_audit.py
Task T014: graph_context.py

# Then integrate:
Task T015: pack.py (depends on T007–T014)
```

### Parallel Example: User Story 4

```bash
# Write failing regression tests first (parallel):
Task T033: test_macro_binding.py
Task T034: test_numeric_xbrl_synthesis.py
Task T035: test_template_dump_guard.py

# Then implement fixes T038–T039 until green
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US2 Taxonomy
4. Complete Phase 4: US1 Investigation Pack
5. **STOP and VALIDATE**: Export 10-item pack; manual triage audit (SC-001, SC-002)

### Incremental Delivery

1. Setup + Foundational → shared models and loaders ready
2. US2 + US1 → investigation MVP (operators can triage tier-1 failures offline)
3. US5 → cohort gate infrastructure (may fail until remediations land)
4. US3 → targeted debug without full repro
5. US4 → agent fixes + regression suite → cohort gate can pass
6. US6 → quality summary integration
7. Polish → quickstart checklist + docs

### Parallel Team Strategy

With multiple developers after Phase 2:

- **Developer A**: US2 → US1 (investigation pack)
- **Developer B**: US5 cohort gate (T020–T026)
- **Developer C**: US3 cohort debug (T027–T031)
- **Developer D**: US4 remediations after US3 smoke validates trace fields

---

## Notes

- Total tasks: **49** (T001–T049)
- Task counts by user story: Setup 3, Foundational 2, US2 3, US1 10, US5 8, US3 5, US4 10, US6 4, Polish 4
- `[P]` tasks touch different files; avoid parallel edits to `pack.py`, `synthesis.py`, or `repro.py`
- Cohort gate thresholds live in manifest YAML, not hard-coded Python (Assumptions)
- Full 200×5 repro explicitly out of scope until cohort gate passes
- v2.0.0 and paper-v1.0 locks MUST remain immutable (FR-011)
