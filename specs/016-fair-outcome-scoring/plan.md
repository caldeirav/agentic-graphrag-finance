# Implementation Plan: Fair Reproduction Outcome Scoring

**Branch**: `016-fair-outcome-scoring` | **Date**: 2026-06-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-fair-outcome-scoring/spec.md`

## Summary

Correct reproduction outcome scoring so answer-GT items map exclusively to `value_alignment` (zero when absent), flat-chunk is judged on retrieval-appropriate criteria, judge-batch resume requires v3 verdicts with full criterion coverage, and custom-judge bundle `v1.1.0` improves GT scorability and corpus feasibility. Ranking metrics remain unchanged; SC-001 (graph-full outcome > flat-chunk) is a target with `OUTCOME_ORDERING_REGRESSION` escalation, not a release block.

## Technical Context

**Language/Version**: Python 3.12+ (existing repo runtime)

**Primary Dependencies**: Typer CLI, Pydantic (`models/benchmark_generation.py`, `models/reproduction.py`), Gemini judge panel (`evaluation/judges/gemini_panel.py`), outcome scoring (`evaluation/judges/outcome_scoring.py`), judge-batch (`evaluation/reproduction/judge_batch.py`), export/report stack (015), bundle publish (`evaluation/generation/bundle.py`)

**Storage**:
- Input: `reports/repro-{tag}/` checkpoints, `configs/judges/gemini_2_5_pro.yaml`
- Bundle: `data/benchmarks/custom-judge/v1.1.0/` (new); `v1.0.0` immutable
- Output: v3 verdicts in `{variant}/results.json`, updated `tables/*.csv`, `report.html`

**Testing**: pytest unit tests for outcome mapping, criteria selection, resume gate, numeric GT classifier; integration judge-batch fixture with v2→v3 migration; bundle publish gate tests; SC acceptance on paper-v1.0 fixtures

**Target Platform**: Local CLI + static HTML report (offline)

**Project Type**: Single-project Python CLI extension under `src/evaluation/`

**Performance Goals**:
- v3 re-judge + export + report < 30 min operator time (judge API bound)
- Bundle v1.1.0 migration script completes in < 5 min on dev split (~200 items)

**Constraints**:
- No ranking metric definition changes (FR-012)
- No full agent re-run unless v1.1.0 changelog flags item (selective re-run)
- SC-001 failure does not block merge
- flat-chunk answer synthesis unchanged (rubric-only fix for chunk-dump gaming)

**Scale/Scope**:
- 5 variants × ~200 dev items (paper-v1.0)
- ~20 HTML items identified as synthesis-fallback inversion in pre-fix analysis
- Bundle migrations: rubric-only routing, required-claims, binding feasibility

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Outcome uses value_alignment only; rubrics penalize wrong-filing citations and ungrounded chunk dumps; feasibility gates block infeasible comparison bindings | **PASS** |
| **II. Structural Semantics Preservation** | No parser or graph changes; bundle fixes are metadata/bindings only | **PASS** |
| **III. Traceability** | Graph variants retain trajectory criteria; flat-chunk exempt per variant contract; v3 verdicts record full criterion list | **PASS** |
| **IV. Separation of Concerns** | Changes in evaluation/judges, evaluation/reproduction, evaluation/generation, report render; no retrieval orchestration changes | **PASS** |
| **V. Code Health & Environment Stability** | Typed criteria contracts; uv lockfile unchanged; judge config versioned in manifest hash | **PASS** |
| **VI. Rigorous Agent Evaluation** | GT-aware outcome, variant-fair judging, bundle v1.1.0 quality gates, stratified report prominence | **PASS** |

**Post-design re-check**: Contracts in `contracts/` define evaluation-layer boundaries only. Bundle publish extends 011 gates without altering ingestion. No constitution violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-fair-outcome-scoring/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── outcome-scoring.md
│   ├── judge-v3-resume.md
│   ├── bundle-v1.1.0.md
│   └── variant-judge-criteria.md
└── tasks.md                # produced by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── evaluation/
│   ├── judges/
│   │   ├── outcome_scoring.py          # MODIFY: VA-only outcome; criteria_for_item variant-aware
│   │   └── gemini_panel.py             # MODIFY: v3 stamp; answer_quality; required_claims prompt
│   ├── generation/
│   │   ├── bundle.py                   # EXTEND: feasibility publish gates
│   │   └── migrate_v1_1_0.py             # NEW: v1.0.0 → v1.1.0 draft + CHANGELOG
│   └── reproduction/
│       ├── judge_batch.py              # MODIFY: v3 + criterion-completeness resume
│       ├── export.py                   # EXTEND: export manifest judge_version_min
│       ├── report_render.py            # EXTEND: outcome-by-profile/stratum prominence; SC-001 note
│       └── report_loader.py            # EXTEND: OUTCOME_ORDERING_REGRESSION aggregation
├── models/
│   └── benchmark_generation.py         # EXTEND: required_claims on GroundTruth
└── cli/commands/
    ├── repro.py                        # VERIFY: --force-rescore docs
    └── benchmark.py                    # VERIFY: publish gates surface

configs/judges/
└── gemini_2_5_pro.yaml                 # MODIFY: anti-dump synthesis; answer_quality; VA rubric

data/benchmarks/custom-judge/
├── v1.0.0/                             # UNCHANGED (audit)
└── v1.1.0/                             # NEW: migrated items + CHANGELOG

releases/paper-v1.0/
└── manifest.yaml                       # MODIFY: custom_judge_version 1.1.0

tests/
├── unit/
│   ├── test_outcome_scoring_fair.py    # NEW
│   ├── test_judge_v3_resume.py         # NEW
│   ├── test_variant_criteria.py        # NEW
│   └── test_bundle_feasibility_gates.py # NEW
└── integration/
    └── test_judge_batch_v2_to_v3.py    # NEW
```

**Structure Decision**: Single-project layout; extends 015 evaluation layer and 011 bundle generation without new packages.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Phases

### Phase A — Outcome scoring (P1, FR-001/002)

1. Remove `synthesis_grounding` fallback in `compute_outcome_scores` for answer-GT items.
2. Missing `value_alignment` → `outcome_score = 0.0`, item stays in denominator.
3. Unit tests: answer-GT with/without VA; rubric-GT exclusion unchanged.

**Files**: `outcome_scoring.py`, `tests/unit/test_outcome_scoring_fair.py`

### Phase B — Judge v3 resume (P1, FR-003/004)

1. Bump `JUDGE_VERSION` to `v3` in `gemini_panel.py`.
2. Replace resume skip in `judge_batch.py` with `should_skip_judging` per `contracts/judge-v3-resume.md`.
3. Integration test: v2 partial verdicts re-judged; v3 complete skipped.

**Files**: `gemini_panel.py`, `judge_batch.py`, `tests/unit/test_judge_v3_resume.py`, `tests/integration/test_judge_batch_v2_to_v3.py`

### Phase C — Variant-aware criteria + rubrics (P2, FR-005/006/009)

1. Implement `criteria_for_item(item, variant_id)` with flat-chunk vs graph sets.
2. Add `answer_quality` criterion to judge config and prompt builder.
3. Extend synthesis_grounding and value_alignment rubric text (anti-dump, required_claims injection).
4. Unit tests per `contracts/variant-judge-criteria.md`.

**Files**: `outcome_scoring.py`, `gemini_panel.py`, `configs/judges/gemini_2_5_pro.yaml`, `tests/unit/test_variant_criteria.py`

### Phase D — Bundle v1.1.0 (P2, FR-007/008/013/014)

1. Implement `is_numeric_answer_gt()` helper.
2. Migration script: rubric-only routing tags, required_claims for narrative answer-GT, binding fixes.
3. Extend `check_publish_gates()` for comparison/reference feasibility.
4. Publish `v1.1.0`, update `releases/paper-v1.0/manifest.yaml`.
5. Document selective re-run in `quickstart.md` and bundle CHANGELOG.

**Files**: `evaluation/generation/migrate_v1_1_0.py`, `bundle.py`, `benchmark_generation.py`, `data/benchmarks/custom-judge/v1.1.0/`

### Phase E — Report & investigation notes (P3, FR-010/011)

1. Promote outcome-by-profile and outcome-by-stratum sections in `report_render.py`.
2. Add `OUTCOME_ORDERING_REGRESSION` and tighten `INCOMPLETE_JUDGE_CRITERIA` in aggregation.
3. Record `min_judge_version: v3` in export manifest metadata.

**Files**: `report_render.py`, `report_loader.py`, `export.py`

### Phase F — Acceptance (SC-001–SC-006)

1. Run quickstart workflow on paper-v1.0 checkpoints.
2. Verify ranking metrics delta < 0.001 (SC-002).
3. Record SC-001 outcome in test fixture or documented operator checklist.

## Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| SC-001 still fails after fixes | Ship with `OUTCOME_ORDERING_REGRESSION`; follow-up on remaining flat-chunk items |
| Judge API cost for full v3 re-score | Resume skip for complete v3; selective agent rerun only for changelog items |
| Migration breaks item ids | CHANGELOG + parent_version in manifest; v1.0.0 retained |
| Required-claims quality | Human review sample in migration; publish gate min 1 max 8 claims |

## Generated Artifacts (this run)

| Artifact | Path |
|----------|------|
| Research | `specs/016-fair-outcome-scoring/research.md` |
| Data model | `specs/016-fair-outcome-scoring/data-model.md` |
| Contracts | `specs/016-fair-outcome-scoring/contracts/*.md` |
| Quickstart | `specs/016-fair-outcome-scoring/quickstart.md` |

**Next command**: `/speckit-tasks` to generate `tasks.md`.
