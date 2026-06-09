# Implementation Plan: Custom-Judge Bundle v2.0 and Unified Task Success

**Branch**: `017-custom-judge-v2` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-custom-judge-v2/spec.md`

## Summary

Re-author custom-judge bundle **v2.0.0** as a **net-new 200-item dev split** on a **refreshed frozen corpus**, with **100% answer-GT** (comparison-structured answers for multi-filing items), **blocking feasibility gates** (including macro-bindability for every item and ≥40 multi-filing items), and a new **paper-v2.0** release lock requiring **full five-variant agent reproduction**. Headline **task_success** for paper-v2.0 equals mean **value_alignment** over n=200 (missing VA = 0); **rubric_alignment** rows are omitted from v2 exports/reports. v1.2.0 remains immutable.

## Technical Context

**Language/Version**: Python 3.12+ (existing repo runtime)

**Primary Dependencies**: Typer CLI (`benchmark_dataset.py`, `repro.py`), Pydantic models (`models/benchmark_generation.py`, `models/evaluation.py`), generation pipeline (`evaluation/generation/`: `bundle.py`, `item_validator.py`, `gemini_item_generator.py`), macro validator (`retrieval/macro/validator.py`), judge panel v3.1 (`evaluation/judges/gemini_panel.py`), reproduction export/report (`evaluation/reproduction/export.py`, `report_render.py`, `report_models.py`)

**Storage**:
- Draft: `data/benchmarks/custom-judge/drafts/{run_id}/`
- Published: `data/benchmarks/custom-judge/v2.0.0/` (new; v1.2.0 immutable)
- Release: `releases/paper-v2.0/manifest.yaml` (new)
- Repro: `reports/repro-paper-v2.0/` (full agent + judge + export)

**Testing**: pytest unit tests for v2 publish gates, answer_type validation, macro-bindability gate, task_success v2 aggregation; integration tests for generate→validate→publish draft; export/report fixture for paper-v2.0 semantics

**Target Platform**: Local CLI + static HTML report (offline eval)

**Project Type**: Single-project Python CLI extension under `src/evaluation/` and `src/cli/commands/`

**Performance Goals**:
- v2.0 generation draft (20 issuers, 220 candidate items) completes within existing governance caps (`max_wall_clock_seconds: 14400`)
- Full paper-v2.0 reproduction remains operator-bound (5 variants × 200 items); no selective agent skip

**Constraints**:
- Net-new pool: no v1.2.0 question text, bindings, or item IDs (FR-006)
- No MRR/nDCG definition changes (out of scope)
- No new judge/LLM model endpoints; reuse judge v3.1 VA + required_claims policy
- 10% stratified manual audit (20 items) required before publish (FR-011)
- rubric_alignment omitted from paper-v2.0 reports (FR-012)

**Scale/Scope**:
- 200 dev items, ≥40 comparison/multi-filing
- 5 system variants × 200 items = 1000 agent runs per full repro
- Refreshed corpus: new seed + filing window via `configs/benchmarks/custom_judge_v2.yaml`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Every v2 item has answer-GT + claims; comparison answers grounded in bound filings; publish gates fail closed on infeasible bindings | **PASS** |
| **II. Structural Semantics Preservation** | Generation uses production Docling/XBRL/graph materialization (011 path); no flat-string-only corpus | **PASS** |
| **III. Traceability** | Full repro retains MLflow trajectories; paper-v2.0 does not alter trajectory schema | **PASS** |
| **IV. Separation of Concerns** | Generation/validation in `evaluation/generation/`; macro gate invokes `retrieval/macro/validator` via adapter; export/report in `evaluation/reproduction/` | **PASS** |
| **V. Code Health & Environment Stability** | `answer_type` and v2 gate results as Pydantic models; uv lockfile; typed publish reports | **PASS** |
| **VI. Rigorous Agent Evaluation** | Unified n=200 task_success on external judge VA; modular bundle registry; paper-v2.0 release lock | **PASS** |

**Post-design re-check**: Contracts define evaluation-layer and bundle boundaries only. Macro validator invoked read-only from generation feasibility harness. No constitution violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-custom-judge-v2/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bundle-v2.0.md
│   ├── task-success-v2.md
│   ├── paper-v2-release.md
│   ├── comparison-gt-template.md
│   └── generation-v2-cli.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── evaluation/
│   ├── generation/
│   │   ├── bundle.py                   # EXTEND: v2 publish gates, scorability report
│   │   ├── item_validator.py           # EXTEND: answer-GT required, answer_type rules
│   │   ├── gemini_item_generator.py    # EXTEND: v2 prompts (comparison_structured)
│   │   ├── feasibility_macro.py        # NEW: macro-bindability gate per item
│   │   └── publish_audit.py            # NEW: 10% audit checklist + sign-off record
│   ├── reproduction/
│   │   ├── export.py                   # MODIFY: task_success v2 = VA-only when bundle ≥2.0
│   │   ├── report_models.py            # MODIFY: metric catalog for v2 semantics
│   │   └── report_render.py            # MODIFY: omit rubric_alignment for paper-v2.0
│   └── judges/
│       └── outcome_scoring.py          # VERIFY: all items use value_alignment path
├── models/
│   ├── benchmark_generation.py         # EXTEND: AnswerType, bundle_schema 2.0
│   └── evaluation.py                   # EXTEND: GroundTruth.answer_type optional field
├── retrieval/macro/
│   └── validator.py                    # REUSE: validate_macro_binding in feasibility
└── cli/commands/
    ├── benchmark_dataset.py            # EXTEND: generate-v2 profile, publish sign-off flags
    └── repro.py                        # EXTEND: --release paper-v2.0 default bundle path

configs/benchmarks/
├── custom_judge_v2.yaml                # NEW: refreshed seed, quotas, multi_filing_floor: 40
└── inspiration_profiles/               # EXTEND: v2 prompt blocks per profile

data/benchmarks/custom-judge/
├── v1.2.0/                             # UNCHANGED (audit)
└── v2.0.0/                             # NEW: net-new items + corpus

releases/
├── paper-v1.0/                         # UNCHANGED
└── paper-v2.0/
    └── manifest.yaml                   # NEW

tests/
├── unit/
│   ├── test_bundle_v2_gates.py         # NEW
│   ├── test_task_success_v2_export.py  # NEW
│   └── test_comparison_gt_template.py  # NEW
└── integration/
    └── test_v2_publish_smoke.py        # NEW
```

**Structure Decision**: Single-project layout; extends 011 generation, 012 repro kit, 016 VA semantics. No migration script — greenfield generator path only.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Phases

### Phase A — v2 data model and bundle contract (P1)

1. Add `AnswerType` enum and optional `answer_type` on `GeneratedBenchmarkItem` / publish manifest `schema_version: "2.0.0"`.
2. Document `contracts/bundle-v2.0.md` gates in `validate_bundle_feasibility()` v2 branch.
3. Reject items with null/empty `ground_truth.answer`; deprecate rubric-only routing for v2 bundles.

**Files**: `models/benchmark_generation.py`, `models/evaluation.py`, `evaluation/generation/item_validator.py`, `evaluation/generation/bundle.py`

### Phase B — Net-new generation pipeline (P1)

1. Add `configs/benchmarks/custom_judge_v2.yaml` (new seed, refreshed filing window, `multi_filing_min: 40`).
2. Extend `gemini_item_generator.py` with v2 profile prompts: mandatory answer, comparison_structured template, claim derivation.
3. Implement `feasibility_macro.py` calling `validate_macro_binding` per item against bundled snapshot.
4. Emit `feasibility_report.json` + `scorability_report.json` on draft completion.

**Files**: `configs/benchmarks/custom_judge_v2.yaml`, `evaluation/generation/gemini_item_generator.py`, `evaluation/generation/feasibility_macro.py`, inspiration profile YAMLs

### Phase C — Publish workflow and operator audit (P2)

1. Implement `publish_audit.py`: stratified 20-item sample list + `--publish-signoff` CLI recording operator approval.
2. Extend `check_publish_gates()` with v2-only gates: macro-bindability, multi_filing floor, answer_gt_coverage.
3. Publish `v2.0.0` to `data/benchmarks/custom-judge/v2.0.0/` with CHANGELOG (thematic lineage notes only).

**Files**: `evaluation/generation/publish_audit.py`, `evaluation/generation/bundle.py`, `cli/commands/benchmark_dataset.py`

### Phase D — paper-v2.0 release lock and full repro (P2)

1. Create `releases/paper-v2.0/manifest.yaml` with new hash fields and `custom_judge_version: "2.0.0"`.
2. Regenerate relevance labels for all 200 items against v2 corpus.
3. Run full agent reproduction on five variants (no selective skip); document in quickstart.

**Files**: `releases/paper-v2.0/manifest.yaml`, repro CLI docs, relevance materialize scripts

### Phase E — task_success v2 export and report (P1)

1. When release manifest pins bundle ≥2.0.0: `_task_success_score` = `outcome_score` (VA) for all eligible items; denominator n=200.
2. Omit `rubric_alignment` rows from headline/stratum exports for paper-v2.0.
3. Update `METRIC_CATALOG` task_success definition for v2 single-criterion semantics.

**Files**: `evaluation/reproduction/export.py`, `report_models.py`, `report_render.py`, unit tests

### Phase F — Acceptance (SC-001–SC-008)

1. Execute quickstart end-to-end on draft → publish → repro → export → report.
2. Verify publish blocked when macro or multi-filing floor fails.
3. Verify v1.2.0 artifacts unchanged.

## Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| Net-new generation fails to reach 200 feasible items | Raise `max_items` headroom; backfill quotas; extend filing window in v2 config |
| Comparison structured answers too brittle | Claim-based partial VA; template validation in `comparison-gt-template.md` |
| Macro gate false negatives | Unit tests against `aapl_macro_snapshot`-style fixtures; gate uses same validator as live agent |
| Full repro cost | Document expected runtime; reuse 013 resume for interruption only (not selective item skip) |
| Operator audit bottleneck | Pre-compute stratified 20-item sample in publish_audit report |

## Generated Artifacts (this run)

| Artifact | Path |
|----------|------|
| Research | `specs/017-custom-judge-v2/research.md` |
| Data model | `specs/017-custom-judge-v2/data-model.md` |
| Contracts | `specs/017-custom-judge-v2/contracts/*.md` |
| Quickstart | `specs/017-custom-judge-v2/quickstart.md` |

**Next command**: `/speckit-tasks` to generate `tasks.md`.
