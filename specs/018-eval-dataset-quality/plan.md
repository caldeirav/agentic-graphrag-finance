# Implementation Plan: Evaluation Dataset Quality Improvement and Management

**Branch**: `018-eval-dataset-quality` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-eval-dataset-quality/spec.md`

## Summary

Add a **human-in-the-loop quality workflow** on top of custom-judge v2.0.0: reproduction-driven review queue, append-only `annotations.jsonl`, in-place overrides/regeneration on an extended draft, comparison boilerplate gate, duplicate-feedback diversity governance, HTML+CSV review packs, selective re-judge with bundle GT override, and publish **v2.0.1** + **paper-v1.1** release lock. v2.0.0 and paper-v1.0 remain immutable.

## Technical Context

**Language/Version**: Python 3.12+ (existing repo)

**Primary Dependencies**: Typer (`benchmark_dataset.py`, `repro.py`), Pydantic (`models/benchmark_generation.py`), generation (`evaluation/generation/`: `bundle.py`, `comparison_gt.py`, `deduplicator.py`, `judge_generator.py`, `item_validator.py`), reproduction (`evaluation/reproduction/`: `report_render.py`, `export.py`, judge batch runner), 014 HTML report patterns

**Storage**:
- Parent bundle: `data/benchmarks/custom-judge/v2.0.0/` (immutable)
- Quality draft: `data/benchmarks/custom-judge/drafts/quality-v2.0.1/`
- Published: `data/benchmarks/custom-judge/v2.0.1/`
- Repro input: `reports/repro-paper-v1.0/`
- New release: `releases/paper-v1.1/`

**Testing**: pytest unit tests for review queue tiers, boilerplate gate, annotation append/apply, override changelog; integration test extend→annotate→apply→publish dry-run; contract test for evaluation import boundary

**Target Platform**: Local CLI + static HTML review pack

**Project Type**: Single-project Python extension under `src/evaluation/generation/review/` and `src/cli/commands/`

**Performance Goals**:
- Review pack export for 20 items < 10s
- Review queue export from 200-item repro < 5s
- Selective re-judge for 20 fixed items << full repro (minutes, not hours)

**Constraints**:
- In-place patch only; no dev_pool re-selection (clarification)
- Annotations sidecar; dev.jsonl mutated only on explicit apply
- JSONL bundle remains eval source of truth; MLflow optional for re-judge logs only
- Existing v2 publish gates + new `boilerplate_comparison_count == 0`

**Scale/Scope**:
- 200 dev items reviewed; target <15% dataset-caused zero-score after pass
- ~66 comparison items receive boilerplate gate + human audit
- paper-v1.1 full 5×200 repro for new baseline checksums

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Corpus spot-check required before apply; boilerplate comparison answers rejected; overrides re-validated against graph index | **PASS** |
| **II. Structural Semantics Preservation** | No corpus regen in quality pass; section paths unchanged unless explicitly overridden | **PASS** |
| **III. Traceability** | Optional MLflow log for selective re-judge; bundle hashes canonical; repro checkpoints reused | **PASS** |
| **IV. Separation of Concerns** | Review logic in `evaluation/generation/review/`; CLI facade only; no retrieval/ingestion imports | **PASS** |
| **V. Code Health & Environment Stability** | Typed Pydantic models for annotations, queue entries, diversity report; uv lockfile | **PASS** |
| **VI. Rigorous Agent Evaluation** | Repro-driven triage; external judge re-score on GT fixes; modular bundle v2.0.1 + paper-v1.1 lock | **PASS** |

**Post-design re-check**: Contracts define evaluation-layer artifacts only. No production ask-path changes. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/018-eval-dataset-quality/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dataset-review-cli.md
│   ├── annotations-sidecar.md
│   ├── review-queue-export.md
│   ├── comparison-boilerplate-gate.md
│   ├── diversity-governance.md
│   └── paper-v1.1-release.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── evaluation/
│   ├── generation/
│   │   ├── review/                      # NEW package
│   │   │   ├── queue.py                 # export-queue priority tiers
│   │   │   ├── annotations.py           # append, load history, apply eligibility
│   │   │   ├── overrides.py             # apply-overrides + changelog
│   │   │   ├── review_pack.py           # HTML + CSV export
│   │   │   ├── quality_summary.py       # quality_pass_summary.json
│   │   │   └── regenerate_item.py       # per-slot Gemini regen
│   │   ├── comparison_gt.py             # EXTEND: is_boilerplate_comparison_answer
│   │   ├── deduplicator.py              # EXTEND: duplicate_feedback hook
│   │   ├── judge_generator.py           # EXTEND: negative examples, diversity caps
│   │   ├── bundle.py                    # EXTEND: v2.0.1 publish, boilerplate gate
│   │   └── item_validator.py            # EXTEND: boilerplate error code
│   └── reproduction/
│       ├── judge_batch.py               # EXTEND: --bundle-override, --item-ids-file
│       └── report_render.py             # REUSE: HTML styling for review_pack
├── models/
│   └── benchmark_generation.py          # EXTEND: ItemAnnotation, ReviewQueueEntry, DiversityReport
└── cli/commands/
    ├── benchmark_dataset.py             # EXTEND: review *, regenerate-item
    └── repro.py                         # EXTEND: judge-batch flags

configs/benchmarks/
├── custom_judge_v2.yaml                 # EXTEND: diversity_governance fields
└── custom_judge_v2_quality.yaml         # NEW: extend config for quality draft

releases/
├── paper-v1.0/                          # UNCHANGED
└── paper-v1.1/                          # NEW manifest + checksums

data/benchmarks/custom-judge/
├── v2.0.0/                              # UNCHANGED
├── v2.0.1/                              # PUBLISHED quality pass
└── drafts/quality-v2.0.1/               # Working draft
```

**Structure Decision**: Single-project extension; new `evaluation/generation/review/` subpackage keeps 011 boundary intact.

## Phase 0: Research

Complete — see [research.md](./research.md). All technical context items resolved; no NEEDS CLARIFICATION remain.

## Phase 1: Design & Contracts

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | Complete |
| Review CLI | [contracts/dataset-review-cli.md](./contracts/dataset-review-cli.md) | Complete |
| Annotations | [contracts/annotations-sidecar.md](./contracts/annotations-sidecar.md) | Complete |
| Review queue | [contracts/review-queue-export.md](./contracts/review-queue-export.md) | Complete |
| Boilerplate gate | [contracts/comparison-boilerplate-gate.md](./contracts/comparison-boilerplate-gate.md) | Complete |
| Diversity | [contracts/diversity-governance.md](./contracts/diversity-governance.md) | Complete |
| paper-v1.1 | [contracts/paper-v1.1-release.md](./contracts/paper-v1.1-release.md) | Complete |
| Operator guide | [quickstart.md](./quickstart.md) | Complete |

## Implementation Phases (for /speckit-tasks)

### P1 — Review infrastructure (US1, US2, US7)

- Models: `ItemAnnotation`, `ReviewQueueEntry`, `OverrideChangelogEntry`
- `review/queue.py`, `review/annotations.py`, `review/review_pack.py`
- CLI: `review export-queue`, `review export-pack`, `review annotate`
- Unit tests: tier sorting, append-only annotations

### P2 — Overrides and validation (US3)

- `review/overrides.py`, `override_changelog.jsonl`
- CLI: `review apply-overrides`
- Integrate v2 gates on apply; integration test 3-item patch

### P3 — Comparison boilerplate gate (US5)

- `is_boilerplate_comparison_answer` + validator integration
- Scorability report extension; finagentbench prompt update
- Unit tests: reject/accept examples from contract

### P4 — Diversity and duplicate feedback (US4)

- `duplicate_feedback.jsonl` in judge_generator
- Diversity config + report; negative prompt examples
- Unit test: issuer cap enforcement

### P5 — Selective re-judge and summary (US6)

- `judge-batch --bundle-override`, `--item-ids-file`
- `review/summary.py`, `quality_pass_summary.json`
- Integration test: fixed items improve VA

### P6 — Publish v2.0.1 + paper-v1.1 (FR-016)

- Publish path for 2.0.1 semver; copy audit sidecars
- `releases/paper-v1.1/manifest.yaml` template
- Full repro + verify-tables documentation

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Success Verification

| Criterion | Verification |
|-----------|--------------|
| SC-001 | Timed 20-item review pack session in quickstart |
| SC-002 | `quality_pass_summary.json` dataset_caused_zero_score_rate < 0.15 |
| SC-003 | rejudge_improved_rate > 0.5 on fixed item set |
| SC-004 | diversity_report duplicate rate vs v2.0.0 baseline |
| SC-005 | scorability boilerplate_comparison_count == 0 |
| SC-007 | override_changelog row per apply; v2.0.0 git diff empty |
