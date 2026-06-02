# Research: Research Reproduction Results Viewer (014)

**Feature**: 014-repro-results-viewer | **Date**: 2026-06-02

## R1 — Report command surface

**Decision**: Add a dedicated read-only subcommand under `agent-query repro` (`repro report`), with explicit input/output options and optional `--format latex-only` mode for scriptable paper pipelines.

**Rationale**: Keeps report generation co-located with reproduction workflows while avoiding changes to existing `run-all`, `judge-batch`, and `export-tables` flows.

**Alternatives considered**:
- New top-level command group — rejected: duplicates reproduction context and docs.
- Implicit report generation during `run-all` — rejected: violates read-only post-run requirement and adds runtime cost.

---

## R2 — Required and optional inputs

**Decision**: Treat these as required: `repro_run.json`, `tables/headline.csv`, `tables/by_profile.csv`, `tables/variant_delta.csv`, `tables/trajectory_audit.csv`, and variant `results.json` files if drill-down is enabled. Treat `tables/headline.tex`, `export_manifest.json`, release manifest metadata, and MLflow links as optional.

**Rationale**: Matches feature request and 012/013 artifact layout while preserving usability on partial outputs.

**Alternatives considered**:
- Require release manifest for all reports — rejected: many operator investigations start from report folders only.
- Require all variant `results.json` always — rejected: partial runs should still be inspectable.

---

## R3 — Static offline report architecture

**Decision**: Generate a single self-contained HTML file by default, with optional co-located assets when configured. No live APIs, no embedded remote scripts, no runtime network dependencies.

**Rationale**: Supports offline inspection and deterministic artifact sharing in CI and paper review loops.

**Alternatives considered**:
- Local server dashboard — rejected for v1 scope and operational complexity.
- Notebook output only — rejected: weaker for non-technical operator workflows.

---

## R4 — Table copy formats and arXiv workflow

**Decision**: Provide one-click copy for LaTeX, CSV, and Markdown per table. LaTeX snippets follow publication-friendly table conventions and include provenance comments (`release_tag`, item counts, exclusion counts where applicable).

**Rationale**: Eliminates manual reformatting friction and preserves consistency with 012 paper table definitions.

**Alternatives considered**:
- CSV-only export — rejected: does not satisfy arXiv paste-ready requirement.
- Full TeX document generation — rejected: too opinionated for varying paper templates.

---

## R5 — Metric rendering and rounding policy

**Decision**: Reuse 012 metric catalog semantics from exported CSVs and apply deterministic display formatting for report presentation only. The viewer does not recompute headline metrics.

**Rationale**: Prevents divergence between exported values and rendered report; simplifies trust and verification.

**Alternatives considered**:
- Recompute metrics from `results.json` in viewer — rejected: risks schema drift and duplicate logic.

---

## R6 — Investigation views and highlight rules

**Decision**: Include variant-level summary cards, primary metric comparisons (`outcome_accuracy`, `ndcg_at_10`, `trajectory_fidelity`), and item drill-down with status filters (`ok`, `degraded`, `pending`, `not_evaluable`) plus flags for structural misses and large deltas vs `graph-full`.

**Rationale**: Directly answers “which variant won, which items failed, and why” from one page.

**Alternatives considered**:
- Aggregate tables only — rejected: insufficient for debugging.
- Full trace replay — rejected: out of scope for v1.

---

## R7 — Error handling for incomplete runs

**Decision**: Fail fast for missing required files with explicit file paths and remediation hints. For optional/missing variant artifacts, render partial report sections with clear warnings rather than aborting.

**Rationale**: Keeps report useful for interrupted or partially completed repro runs.

**Alternatives considered**:
- Hard-fail on any missing input — rejected: blocks recovery workflows.

---

## R8 — Test strategy

**Decision**: Add unit tests for loader/formatters, contract tests for CLI output contracts, and integration smoke test that renders HTML from fixture or `paper-smoke` output with networking disabled.

**Rationale**: Enforces SC-003/SC-004 and prevents regressions in paper copy outputs.

**Alternatives considered**:
- Snapshot tests only — rejected: misses CLI and offline behavior guarantees.

