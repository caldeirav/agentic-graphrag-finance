---
description: "Task list for research reproduction results viewer (014)"
---

# Tasks: Research Reproduction Results Viewer

**Input**: Design documents from `specs/014-repro-results-viewer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md; features **012** and **013** merged on `main`; branch `014-repro-results-viewer`

**Tests**: Unit, contract, and integration tests per plan testing strategy and success criteria SC-002–SC-004.

**Organization**: Foundational loader/models block all stories; **US1 paper table copy → US2 run summary/comparison → US3 item drill-down → US4 investigation aids/offline**; polish adds docs and regression sweep. US1–US4 share `report_render.py` — implement in story order to reduce merge conflicts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no blocking deps on incomplete tasks)
- **[USn]**: User story label

## Path Conventions

- New: `src/evaluation/reproduction/report_models.py`, `report_loader.py`, `report_formatters.py`, `report_render.py`, `report_errors.py`
- Extend: `src/cli/commands/repro.py`, `src/evaluation/reproduction/__init__.py`
- Template: `templates/reproduction_report.html` (self-contained static HTML shell; no CDN)
- Tests: `tests/unit/`, `tests/contract/`, `tests/integration/`
- Docs: `docs/research-reproduction.md`, `README.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Report module scaffold and shared errors

- [ ] T001 Create `src/evaluation/reproduction/report_errors.py` with `ReportInputError` and `ReportRenderError` carrying file paths per `contracts/report-input-schema.md`
- [ ] T002 [P] Create `templates/reproduction_report.html` static shell with placeholder sections (summary, tables, comparison, drill-down) per `contracts/report-output.md`
- [ ] T003 [P] Export report public entrypoints from `src/evaluation/reproduction/__init__.py` per `plan.md` project structure

**Checkpoint**: `from evaluation.reproduction.report_errors import ReportInputError` resolves

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed report models, formatters, and artifact loader — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T004 Implement Pydantic report view models (`ReproOutputBundle`, `RunSummaryView`, `PaperTableView`, `VariantComparisonView`, `ItemResultRecord`, `ReportArtifact`) in `src/evaluation/reproduction/report_models.py` per `data-model.md`
- [ ] T005 [P] Implement metric display formatters and LaTeX numeric escaping helpers in `src/evaluation/reproduction/report_formatters.py` per `research.md` R4–R5
- [ ] T006 Implement `load_repro_report_bundle(input_dir, *, manifest_path=None)` in `src/evaluation/reproduction/report_loader.py`: hard-fail on missing `repro_run.json` or required CSVs; treat missing `{variant}/results.json` as warnings with incomplete variant markers per `research.md` R7 and `contracts/report-input-schema.md`; load optional artifacts when present
- [ ] T007 [P] Add unit tests `tests/unit/test_repro_report_loader.py` for required-file errors, optional-file warnings, CSV header validation against 012 paper-table-export columns, and partial-run behavior when `{variant}/results.json` is missing (warning, not exit 2) per `research.md` R7

**Checkpoint**: `uv run pytest tests/unit/test_repro_report_loader.py -q` passes

---

## Phase 3: User Story 1 - Paper-Ready Table Export (Priority: P1) 🎯 MVP

**Goal**: Render paper tables with one-click LaTeX/CSV/Markdown copy and `--format latex-only` stdout mode

**Independent Test**: Generate report from smoke output; copied LaTeX headline values match `tables/headline.csv` within documented rounding (SC-002)

### Tests for User Story 1

- [ ] T008 [P] [US1] Add unit tests `tests/unit/test_repro_report_latex_copy.py` for booktabs LaTeX snippet generation, provenance comments, and CSV value fidelity per `contracts/report-output.md`
- [ ] T009 [P] [US1] Add contract test `tests/contract/test_repro_report_cli.py` for `--format latex-only --table headline` stdout shape and exit codes per `contracts/report-cli.md`

### Implementation for User Story 1

- [ ] T010 [US1] Implement `build_paper_table_views(bundle)` returning `PaperTableView[]` with embedded `latex_copy`, `csv_copy`, `markdown_copy` in `src/evaluation/reproduction/report_render.py` per FR-006–FR-008
- [ ] T011 [US1] Implement LaTeX booktabs table builder in `src/evaluation/reproduction/report_formatters.py` with caption comments (`release_tag`, item counts, exclusions) per `research.md` R4
- [ ] T012 [US1] Add HTML paper-table section renderer with copy buttons (inline JS, no network) in `src/evaluation/reproduction/report_render.py` using `templates/reproduction_report.html`
- [ ] T013 [US1] Add `repro report` subcommand stub in `src/cli/commands/repro.py` with `--input`, `--output`, `--format`, `--table` flags; wire `latex-only` stdout path per `contracts/report-cli.md`
- [ ] T014 [US1] Implement `--table` filter (repeatable) limiting rendered/copied tables to `headline`, `by_profile`, `variant_delta`, `trajectory_audit` in `src/cli/commands/repro.py`
- [ ] T015 [US1] Render optional `tables/headline.tex` compare panel (read-only hint vs generated LaTeX) when present; omit section when absent per FR-004 in `src/evaluation/reproduction/report_render.py`

**Checkpoint**: `uv run agent-query repro report --input reports/repro-paper-smoke --format latex-only --table headline` emits paste-ready LaTeX; unit/contract tests pass

---

## Phase 4: User Story 2 - Run Summary and Variant Comparison (Priority: P1)

**Goal**: Single-page orientation — release metadata, timing, exclusion counts, primary metric comparison across variants

**Independent Test**: Open generated HTML; run summary and bar-style comparison for `outcome_accuracy`, `ndcg_at_10`, `trajectory_fidelity` visible without opening raw JSON (US2 acceptance)

### Tests for User Story 2

- [ ] T016 [P] [US2] Add unit tests `tests/unit/test_repro_report_summary.py` for `RunSummaryView` and `VariantComparisonView` derivation from fixture bundle in `src/evaluation/reproduction/report_render.py`

### Implementation for User Story 2

- [ ] T017 [US2] Implement `build_run_summary(bundle)` aggregating release tag, duration, defer/resume flags, per-variant counts (`excluded_incomplete`, `excluded_degraded`, `excluded_pending_judge`) in `src/evaluation/reproduction/report_render.py` per FR-005 and `data-model.md`
- [ ] T018 [US2] Implement `build_variant_comparison(bundle)` from `headline.csv` for primary metrics across standard five variants in `src/evaluation/reproduction/report_render.py` per FR-010
- [ ] T019 [US2] Render run summary and variant comparison sections (inline SVG/CSS bars, offline-safe) into `templates/reproduction_report.html` via `src/evaluation/reproduction/report_render.py`
- [ ] T020 [US2] Wire full `--format html` default path in `src/cli/commands/repro.py` writing `<input>/report.html` (or `--output`) with summary + tables + comparison sections
- [ ] T021 [US2] Render optional `export_manifest.json` metadata section in run summary when present; omit when absent per FR-004 in `src/evaluation/reproduction/report_render.py`

**Checkpoint**: HTML report from smoke output shows summary cards and metric comparison without manual CSV/JSON inspection

---

## Phase 5: User Story 3 - Per-Item Investigation (Priority: P2)

**Goal**: Filterable per-variant item tables with expandable detail and judge-status highlights (FR-013)

**Independent Test**: Filter to `judge_status=degraded` for one variant; verify scores, excerpts, and visual highlights for `degraded`/`pending`/`not_evaluable` rows match `{variant}/results.json` (US3 acceptance)

### Tests for User Story 3

- [ ] T022 [P] [US3] Add unit tests `tests/unit/test_repro_report_items.py` mapping `BenchmarkResult` rows to `ItemResultRecord` with truncated answer, citation counts, and status highlight classes for `degraded`/`pending`/`not_evaluable` per FR-013 in `src/evaluation/reproduction/report_loader.py` or `report_render.py`

### Implementation for User Story 3

- [ ] T023 [US3] Implement `load_variant_item_records(bundle)` parsing per-variant `results.json` when present into `ItemResultRecord[]` in `src/evaluation/reproduction/report_loader.py` per `contracts/report-input-schema.md` (skip drill-down for variants without checkpoints)
- [ ] T024 [US3] Render item drill-down tables per variant with client-side filters (variant, profile, judge status) in `src/evaluation/reproduction/report_render.py` and `templates/reproduction_report.html` per FR-011
- [ ] T025 [US3] Add visual row highlighting and quick-filter chips for `degraded`, `pending`, and `not_evaluable` in `templates/reproduction_report.html` (inline CSS/JS only) per FR-013
- [ ] T026 [US3] Add expandable row detail (answer excerpt, citation summary, trajectory pointer to source JSON path) in `templates/reproduction_report.html` per FR-012
- [ ] T027 [US3] Add `--max-item-rows` soft cap in `src/cli/commands/repro.py` per `contracts/report-cli.md`

**Checkpoint**: Drill-down filterable with status highlights; expanded rows show truncated answers matching source JSON

---

## Phase 6: User Story 4 - Investigation Aids and Offline Use (Priority: P2)

**Goal**: Binding-miss and baseline-delta flags, optional MLflow links, fully offline static report

**Independent Test**: Generate report with network disabled; open HTML locally; binding-miss and high-delta flags work (US4 acceptance, SC-003/SC-004)

### Tests for User Story 4

- [ ] T028 [P] [US4] Add unit tests `tests/unit/test_repro_report_flags.py` for binding-miss and high-delta-vs-`graph-full` flag rules in `src/evaluation/reproduction/report_render.py` per FR-014

### Implementation for User Story 4

- [ ] T029 [US4] Implement investigation flag computation (structural binding miss, metric delta vs `graph-full`) with configurable `--delta-threshold` (default `0.10` per `research.md` R6) in `src/evaluation/reproduction/report_render.py` per FR-014
- [ ] T030 [US4] Render optional MLflow parent run links in run summary when ids present in `repro_run.json` (external href only, not embedded UI) per FR-004 and spec US4
- [ ] T031 [US4] Ensure report output is self-contained: inline assets, no CDN scripts, relative paths only in `src/evaluation/reproduction/report_render.py` per FR-015 and `research.md` R3
- [ ] T032 [US4] Add optional `--manifest` provenance block loader in `src/evaluation/reproduction/report_loader.py` and summary display per `contracts/report-cli.md`
- [ ] T033 [US4] Add integration test `tests/integration/test_repro_report_smoke.py`: render HTML from `reports/repro-paper-smoke` or fixture copy offline; assert file exists, contains headline table and summary (SC-004)

**Checkpoint**: `uv run pytest tests/integration/test_repro_report_smoke.py -q` passes; report opens offline in browser

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, contract coverage, and regression validation

- [ ] T034 [P] Extend `tests/contract/test_repro_report_cli.py` for missing required input exit code 2 and invalid CSV exit behavior per `contracts/report-cli.md`
- [ ] T035 [P] Update `docs/research-reproduction.md` with `repro report` workflow, LaTeX copy, and troubleshooting cross-link to `specs/014-repro-results-viewer/quickstart.md`
- [ ] T036 [P] Update `README.md` Path B section with one-line `repro report` example after reproduction completes
- [ ] T037 Run full repro-report pytest sweep: `uv run pytest tests/unit/test_repro_report_* tests/contract/test_repro_report_cli.py tests/integration/test_repro_report_smoke.py -q`
- [ ] T038 Validate quickstart commands in `specs/014-repro-results-viewer/quickstart.md` against local smoke output directory

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational — MVP (LaTeX/table copy)
- **US2 (Phase 4)**: Depends on Foundational + US1 render scaffolding in `report_render.py`
- **US3 (Phase 5)**: Depends on Foundational; integrates into HTML from US2
- **US4 (Phase 6)**: Depends on US3 item records; adds binding/delta flags and offline hardening
- **Polish (Phase 7)**: Depends on US1–US4 desired for release

### User Story Dependencies

| Story | Depends on | Independently testable via |
|-------|------------|----------------------------|
| US1 | Foundational | `latex-only` stdout + LaTeX unit tests |
| US2 | Foundational, US1 render shell | HTML summary/comparison sections |
| US3 | Foundational | Item mapping unit tests + drill-down HTML with FR-013 status highlights |
| US4 | US3 | Binding/delta flag unit tests + offline integration smoke |

### Parallel Opportunities

- Phase 1: T002, T003 parallel after T001
- Phase 2: T005, T007 parallel with T004/T006 sequential core
- US1 tests T008, T009 parallel before T010–T015
- US2 test T016 parallel with US1 completion if different author
- US3 test T022 parallel with US2 implementation (different files)
- US4 test T028 parallel with US3 implementation
- Polish T034–T036 parallel

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task T008: tests/unit/test_repro_report_latex_copy.py
Task T009: tests/contract/test_repro_report_cli.py

# Then implementation (sequential on report_render.py):
Task T010 → T011 → T012 → T013 → T014 → T015
```

---

## Parallel Example: Foundational

```bash
Task T004: report_models.py
Task T005: report_formatters.py   # parallel with T004
Task T006: report_loader.py       # after T004 models exist
Task T007: test_repro_report_loader.py  # after T006
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2 (Setup + Foundational)
2. Complete Phase 3 (US1): LaTeX/table copy + `latex-only` CLI
3. **STOP and VALIDATE**: SC-002 LaTeX fidelity on smoke output
4. Demo paste into LaTeX draft before building full HTML investigation UI

### Incremental Delivery

1. US1 → paper table copy (LaTeX pipeline)
2. US2 → add summary + comparison to HTML report
3. US3 → add item drill-down
4. US4 → investigation aids + offline smoke test
5. Polish → docs + full pytest sweep

### Suggested MVP Scope

**User Story 1 only** (Phases 1–3): delivers core arXiv copy workflow (`repro report --format latex-only`) before full investigation HTML.

---

## Notes

- Do **not** re-run judge, agent, or `export-tables` from report code paths (FR-002)
- Do **not** recompute headline aggregates — consume 012 CSV exports as source of truth
- Prefer stdlib HTML/templating; avoid new dependencies unless template complexity forces Jinja2 (document in plan if added)
- `report_render.py` is shared — coordinate story merges in order US1 → US2 → US3 → US4
