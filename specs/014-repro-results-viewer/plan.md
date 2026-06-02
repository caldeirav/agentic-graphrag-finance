# Implementation Plan: Research Reproduction Results Viewer

**Branch**: `014-repro-results-viewer` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-repro-results-viewer/spec.md`

## Summary

Add a read-only reproduction reporting surface that turns `reports/repro-{tag}/` artifacts into one self-contained investigation page. The plan adds a new `agent-query repro` reporting command, report-focused models/loaders, static HTML generation, and copy-ready LaTeX/CSV/Markdown table exports for paper workflows, while reusing existing 012/013 output schema and keeping evaluation execution out of scope.

## Technical Context

**Language/Version**: Python 3.12+ (existing repo runtime)

**Primary Dependencies**: Existing CLI stack (Typer), existing reproduction models/loaders, stdlib templating and serialization utilities, existing table export contract from 012

**Storage**:
- Input: existing filesystem artifacts in `reports/repro-{tag}/`
- Output: static `report.html` (+ optional `assets/` directory)
- No database, no network calls

**Testing**: pytest unit + integration smoke on fixture or `paper-smoke` outputs; contract tests for CLI I/O and LaTeX copy output fidelity

**Target Platform**: Local CLI + desktop browser (offline post-generation)

**Project Type**: Single-project Python CLI feature under evaluation/reproduction + docs

**Performance Goals**:
- Report generation <= 30s on smoke fixtures (SC-003)
- First meaningful render in browser without loading external resources

**Constraints**:
- Must not re-run judge/agent/eval workflows (FR-002)
- Must preserve 012 metric catalog naming/semantics and rounding rules (FR-006)
- Works offline after generation (FR-015)

**Scale/Scope**:
- Typical: 5 variants, 200+ items, up to thousands of citations
- Must remain usable for item-level investigation via filtering/highlighting

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Report is read-only over existing repro artifacts; no inferred metrics outside exported contracts | **PASS** |
| **II. Structural Semantics Preservation** | No parser/graph changes; report consumes already structured exports | **PASS** |
| **III. Traceability** | Run summary includes ids/paths and optional MLflow links; item drill-down references source rows | **PASS** |
| **IV. Separation of Concerns** | Reporting lives in evaluation/reproduction CLI; retrieval and judge execution are untouched | **PASS** |
| **V. Code Health & Environment Stability** | Typed report models at file boundaries; uv/lockfile workflow unchanged | **PASS** |
| **VI. Rigorous Agent Evaluation** | Viewer surfaces evaluation outcomes without changing scoring logic | **PASS** |

**Post-design re-check**: Phase 1 artifacts keep report generation as a read-only consumer and introduce no cross-layer import violations.

## Project Structure

### Documentation (this feature)

```text
specs/014-repro-results-viewer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── report-cli.md
│   ├── report-input-schema.md
│   └── report-output.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── cli/
│   └── commands/
│       └── repro.py                      # EXTEND: report/view subcommand
├── evaluation/
│   └── reproduction/
│       ├── report_loader.py              # NEW: load + validate report inputs
│       ├── report_models.py              # NEW: typed report view models
│       ├── report_render.py              # NEW: html + latex/csv/md renderers
│       └── report_formatters.py          # NEW: metric/value formatting rules

templates/
└── reproduction_report.html.j2           # NEW: static report template (or equivalent)

tests/
├── contract/test_repro_report_cli.py
├── unit/test_repro_report_loader.py
├── unit/test_repro_report_latex_copy.py
└── integration/test_repro_report_smoke.py
```

**Structure Decision**: Single-project CLI extension within existing evaluation/reproduction package. No new service boundary.

## Complexity Tracking

No constitution violations requiring exceptions are introduced.

## Phase 0: Research

Completed in [research.md](./research.md):
- Report input canonical schema and required vs optional files
- Copy formats and LaTeX table rules for arXiv workflow
- Visualization and interaction defaults that remain static/offline
- Error handling and partial-run display behavior

## Phase 1: Design

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| CLI contract | [contracts/report-cli.md](./contracts/report-cli.md) |
| Input contract | [contracts/report-input-schema.md](./contracts/report-input-schema.md) |
| Output contract | [contracts/report-output.md](./contracts/report-output.md) |
| Operator quickstart | [quickstart.md](./quickstart.md) |

## Implementation phases (for /speckit-tasks)

### Phase A — Loader and typed report model

1. Add typed models for run summary, table blocks, per-item investigation rows
2. Implement report loader for required/optional artifact files
3. Add validation errors with actionable path-specific messages

### Phase B — Renderers and copy formats

1. Build HTML renderer for run summary, table section, comparison charts, drill-down
2. Build copy exporters for LaTeX, CSV, Markdown table snippets
3. Add `--format latex-only` output path for scripting

### Phase C — CLI integration and investigation aids

1. Add `repro report` (or `repro view`) subcommand options
2. Wire threshold-based highlight rules and status filters
3. Add smoke and contract tests against fixture/paper-smoke outputs
4. Update docs links for report workflow in README/docs/research-reproduction.md

## Phase 2

Task breakdown and sequencing will be generated by `/speckit-tasks`.
