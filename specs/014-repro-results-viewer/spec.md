# Feature Specification: Research Reproduction Results Viewer

**Feature Branch**: `014-repro-results-viewer`

**Created**: 2026-06-03

**Status**: Draft

**Input**: Build a research reproduction results viewer: a CLI command that reads a completed repro output directory (`reports/repro-{release_tag}/`) and generates a single self-contained HTML report page for investigating a run and copying paper-ready tables into an arXiv LaTeX manuscript. Depends on features 012/013 reproduction kit; read-only over existing artifacts; does not re-run evaluation or change export schema except optional provenance fields.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Paper-Ready Table Export (Priority: P1)

A researcher finishing a reproduction run wants to copy headline benchmark tables and ablation deltas into an arXiv LaTeX manuscript without manually reformatting CSV files or reconciling metric names.

**Why this priority**: The primary deliverable of reproduction is publishable numbers; friction at copy-paste time blocks paper submission.

**Independent Test**: Given a completed repro output directory with exported `tables/` CSVs, generate the report and copy the headline table as LaTeX; verify metric names, row counts, and numeric values match the source CSV within documented rounding rules.

**Acceptance Scenarios**:

1. **Given** a completed repro with `tables/headline.csv`, **When** the operator generates the report and copies the headline table as LaTeX, **Then** the snippet uses publication-style tabular formatting, includes caption metadata (release tag, item counts), and numeric values match the CSV source.
2. **Given** `tables/by_profile.csv` and `tables/variant_delta.csv` exist, **When** the report is generated, **Then** each table is rendered on the page with one-click copy options for LaTeX, CSV, and Markdown.
3. **Given** the operator passes a LaTeX-only output mode, **When** the command runs, **Then** paste-ready LaTeX for selected tables is written to standard output for scripting pipelines.

---

### User Story 2 - Run Summary and Variant Comparison (Priority: P1)

An evaluation engineer opening a reproduction output folder wants a single page that answers “which variant won, how long did it run, and how do primary metrics compare across variants?” without opening multiple JSON and CSV files.

**Why this priority**: Run-level orientation is the first step in every investigation session.

**Independent Test**: Generate a report from a smoke or full repro directory; verify run summary, per-variant item counts, exclusion counts, and a visual comparison of primary metrics appear without manual file navigation.

**Acceptance Scenarios**:

1. **Given** `repro_run.json` and exported tables, **When** the report is generated, **Then** the page shows release tag, run identifier, wall-clock duration, defer-judge/resume flags when recorded, and item counts per variant.
2. **Given** trajectory audit and per-item results, **When** the summary section renders, **Then** excluded incomplete, degraded, and pending-judge counts are visible per variant.
3. **Given** headline metrics for all five standard variants, **When** the comparison section renders, **Then** primary metrics (`outcome_accuracy`, `ndcg_at_10`, `trajectory_fidelity`) are compared visually across `graph-full`, `flat-chunk`, and ablation variants.

---

### User Story 3 - Per-Item Investigation (Priority: P2)

An operator investigating unexpected scores wants to filter and inspect individual benchmark items—judge status, scores, truncated answers, and failure reasons—grouped by variant.

**Why this priority**: Aggregate tables hide item-level failures; debugging requires drill-down without reading raw JSON by hand.

**Independent Test**: Generate a report from a repro with mixed judge outcomes; filter to degraded items for one variant and verify scores, status, and answer excerpts match `results.json` for those items.

**Acceptance Scenarios**:

1. **Given** per-variant `results.json` files, **When** the item drill-down section loads, **Then** each variant shows a filterable table with item id, inspiration profile, judge status, outcome and rubric scores, validation status, and failure or exclusion reason when applicable.
2. **Given** an item row, **When** the operator expands it, **Then** a truncated answer excerpt, citation summary, and trajectory summary (or pointer to full result record) are shown.
3. **Given** items with judge status `degraded`, `pending`, or `not_evaluable`, **When** the report renders, **Then** those rows are visually highlighted and filterable by status.

---

### User Story 4 - Investigation Aids and Offline Use (Priority: P2)

A researcher working on a laptop without network access after a long repro wants to open one HTML file locally and investigate binding misses and large performance gaps versus the `graph-full` baseline.

**Why this priority**: Repro outputs are often reviewed offline; the report must be self-contained.

**Independent Test**: Generate the report with network disabled; open the HTML file in a browser and use investigation filters without errors.

**Acceptance Scenarios**:

1. **Given** a completed repro directory, **When** the report is generated, **Then** output is a static HTML page (with optional co-located assets folder) that opens and functions fully offline.
2. **Given** item results with structural binding misses or large metric deltas versus `graph-full`, **When** investigation aids are enabled, **Then** those items are flagged for review.
3. **Given** optional MLflow parent run identifiers in run metadata, **When** the summary renders, **Then** deep links to MLflow are shown as optional references (not required for core report function).

---

### Edge Cases

- **Missing optional inputs**: Report generation succeeds with required inputs only; optional files (`headline.tex`, `export_manifest.json`) are omitted from sections when absent.
- **Partial repro (pending judge items)**: Summary and audit sections show pending counts; headline copy includes exclusion footnotes consistent with 012 export rules.
- **Incomplete variant directory**: Variants with no `results.json` are listed as incomplete in the summary; other variants still render.
- **Corrupt or unreadable input file**: Command fails with a clear message naming the file and variant—no partial silent HTML.
- **Very large result sets**: Item drill-down remains usable via filtering and pagination or virtual scrolling (operator-configurable limit for v1 smoke acceptable).
- **Release manifest unavailable**: Report still generates from on-disk repro artifacts; provenance block notes manifest as unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a reproduction subcommand that accepts a completed repro output directory path and generates a static HTML report.
- **FR-002**: The command MUST read only existing reproduction artifacts; it MUST NOT re-run agents, judges, or table export.
- **FR-003**: Required inputs MUST include run state at output root (`repro_run.json`) and exported table CSVs (`headline`, `by_profile`, `variant_delta`, `trajectory_audit`). Per-variant item result checkpoints (`{variant}/results.json`) are required for full item drill-down; missing variant checkpoints MUST NOT fail report generation—those variants appear as incomplete with warnings (per research R7).
- **FR-004**: Optional inputs MUST be supported when present: pre-generated LaTeX headline, export manifest, release manifest metadata, MLflow parent run identifiers.
- **FR-005**: The report MUST include a run summary section with release tag, run identifier, duration, reproduction mode flags (defer judge, resume) when recorded, and per-variant item and exclusion counts.
- **FR-006**: The report MUST render paper tables (`headline`, `by_profile`, `variant_delta`, `trajectory_audit`) as styled HTML tables consistent with the 012 paper-table-export metric catalog and rounding conventions.
- **FR-007**: Each rendered paper table MUST offer one-click copy in LaTeX (publication tabular style), CSV, and Markdown formats.
- **FR-008**: LaTeX snippets MUST be paste-ready for arXiv manuscripts: tabular structure suitable for standard academic packages, numeric formatting compatible with common LaTeX number columns, and caption comments documenting release tag and item counts.
- **FR-009**: The command MUST support a LaTeX-only output mode that writes selected table LaTeX to standard output for automation.
- **FR-010**: The report MUST include a variant comparison visualization for primary metrics across standard reproduction variants.
- **FR-011**: The report MUST include per-variant item drill-down with filtering by judge status, profile, and variant.
- **FR-012**: Item drill-down MUST show truncated answer text and citation summary; expanded rows MUST show trajectory summary or explicit reference to the full item record on disk.
- **FR-013**: The report MUST visually highlight and allow filtering of items with judge status `degraded`, `pending`, or `not_evaluable`.
- **FR-014**: Investigation aids MUST flag items with structural binding misses and items whose primary metrics differ substantially from the `graph-full` baseline for the same item (threshold documented in operator guide).
- **FR-015**: Generated output MUST work fully offline after generation (no live MLflow embedding or network dependency in v1).
- **FR-016**: The command MUST fail fast with actionable errors when required inputs are missing or invalid.
- **FR-017**: Optional provenance fields MAY be added to release manifest for report generation metadata without breaking existing reproduction workflows.

### Key Entities

- **Reproduction output bundle**: Directory containing run state, per-variant results, and exported tables from a single reproduction execution.
- **Run summary**: Aggregated metadata—timing, release tag, mode flags, variant completion, exclusion counts.
- **Paper table view**: Presentation of exported CSV tables with multi-format copy actions.
- **Variant comparison**: Cross-variant metric visualization for primary headline metrics.
- **Item result record**: Per-benchmark-item scores, judge status, answer excerpt, validation and structural metrics from variant checkpoints.
- **Report artifact**: Self-contained HTML page plus optional static assets produced by the viewer command.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can open one generated HTML file after `paper-live-smoke` or `paper-v1.0` reproduction and answer “which variant won, which items failed, and what to paste into Table 1” in under 5 minutes without opening raw JSON manually.
- **SC-002**: Copied LaTeX for the headline table matches source CSV numeric values for all included metrics (within documented rounding tolerance).
- **SC-003**: Report generation from fixture or smoke reproduction output completes in under 30 seconds on a reference developer machine without network access.
- **SC-004**: Automated smoke test verifies HTML is produced from fixture or paper-smoke output with no network dependency.
- **SC-005**: At least 90% of operators in a dry-run checklist can successfully copy a headline table into a LaTeX draft on first attempt without reformatting.

## Assumptions

- Reproduction outputs follow the 012/013 layout: `repro_run.json`, `tables/*.csv`, `{variant}/results.json`.
- Standard five variants (`graph-full`, `flat-chunk`, three ablations) are the default comparison set; additional variants render if present on disk.
- Metric names and aggregation exclusions match the 012 paper-table-export contract; the viewer does not recompute aggregates—it presents exported values.
- Operators use a modern desktop browser to open the static HTML report.
- MLflow links are optional convenience references; core investigation does not require MLflow UI access in v1.
- v1 scope is static report generation only—no hosted dashboard, result editing, or judge re-execution.

## Dependencies

- Feature 012 research reproduction kit (table export schema, variant layout).
- Feature 013 benchmark eval acceleration (defer-judge pending states, run checkpoints)—viewer must display pending judge counts correctly.

## Out of Scope (v1)

- Hosted web server or live dashboard
- Embedded MLflow UI or live trace replay
- Editing or mutating reproduction results
- Re-running judge or agent evaluation from the viewer
- Network-required features after report generation
