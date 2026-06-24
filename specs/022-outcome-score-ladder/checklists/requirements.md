# Specification Quality Checklist: Outcome Score Ladder (022)

**Feature**: [spec.md](../spec.md)  
**Created**: 2026-06-24

## Content Quality

- [x] Requirements focus on outcome_score (value_alignment), not upstream-only metrics
- [x] Builds on 021/022 without re-litigating temporal rebind
- [x] User stories A–E map to ROI-ordered phases with explicit defer rule for segment graph
- [x] All mandatory sections completed in spec.md

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers
- [x] Success criteria SC-A through SC-E measurable on 26-item cohort
- [x] Phase gates require fresh cohort re-run (not replay)
- [x] Out of scope documented (judge swap, full paper repro, live overrides)

## Feature Readiness

- [x] tasks.md covers phases A–E with unit tests + cohort gate per phase
- [x] Contracts for ratio pair, point fact, phase gate result
- [x] Fixtures: `cohort_phase_targets.json` with primary item_ids per phase
- [x] Gate script documented in quickstart.md
- [x] Constitution / Principle VII alignment in plan.md

## Notes

- SC-A through SC-E validated by operator via cohort-debug + judge-batch, not CI alone.
- Phase E deferrable until SC-C passes or SC-001 gate requires segment lift.
- Record each phase result in `research.md` before starting next phase.
