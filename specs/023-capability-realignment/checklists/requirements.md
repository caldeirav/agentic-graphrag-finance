# Specification Quality Checklist: Capability Realignment (023)

**Feature**: [spec.md](../spec.md)  
**Created**: 2026-06-24

## Content Quality

- [x] Problem ties to 022-E failure and Principle VII explicitly
- [x] User stories ordered: policy → LLM skill → retrieval → validation → retirement
- [x] Supersedes 022 heuristic intent without rewriting history
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers
- [x] SC-001–SC-006 measurable on 26-item cohort
- [x] Out of scope lists “more regex” and judge swap
- [x] Assumes fresh cohort re-run

## Feature Readiness

- [x] tasks.md covers M1–M3 with tests + cohort gates
- [x] plan.md Complexity Tracking documents exceptions
- [x] contracts define numeric path policy
- [x] constitution-vii.md checklist included

## Notes

- Implementation MUST NOT proceed without M1 telemetry (SC-004) — otherwise gates are unmeasurable.
- SC-003 (zero LLM fallback) is stricter than SC-001 (outcome_gt0) and runs first.
