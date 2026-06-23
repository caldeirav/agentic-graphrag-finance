# Research: XBRL Numeric Binding & Computation (021)

**Date**: 2026-06-23  
**Baseline**: Cohort re-run after 020 (`reports/cohort-xbrl-numeric-debug`)

## 020 Outcome Summary

| Metric | paper-v1.1 replay | After 020 re-run |
|--------|-------------------|------------------|
| Template dumps | 18/26 | ~2/26 |
| Abstention-like | low | ~19/26 |
| Wrong numeric claims | 8/26 | ~6/26 |
| outcome_score > 0 | 0/26 | 0/26 |
| MRR ≥ 0.5 | 25/26 | 25/26 |
| Weakest judge (mode) | mixed | routing_decisions 18/26 |

## Root Cause (post-020)

1. **Binding**: Latest 10-Q bound for “fiscal year 2025” questions; synthesis abstains honestly.
2. **Concept**: Wrong XBRL line selected despite high MRR (`OtherAssetsFairValueDisclosure`, Q1 equity vs FY equity).
3. **Computation**: Delta/ratio/% questions answered with single level fact or abstention.
4. **Legacy overrides**: `_correct_numeric_from_xbrl` still injects deterministic wrong answers in live path.

## Evidence Examples

| item_id | Issue | GT (abbrev) | Answer pattern |
|---------|-------|-------------|----------------|
| 0428 | Wrong period bound | segment revenue FY2025 | “does not contain… 2026 Q1” |
| 0436 | Wrong period/concept | equity FY2025 | $269.81B as of Apr 2025 |
| 0495 | Wrong period | cash end of period | 2026-04-01 fact |
| 0536 | Wrong concept | asset change (millions) | unrelated fair value fact |
| 0667 | Missing computation | YoY % net income | abstention |

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Structured `TemporalScopeIntent` before validator | Prompt hints alone insufficient (020) |
| Python for arithmetic | Judge expects precise GT numbers; LLM math fails |
| Catalog + pre-filter + LLM pick | Principle VII; reduces wrong concept vs pure LLM |
| Gate live numeric correctors | Worse VA than abstention |

## Cohort

Same 26 ids: `specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json`

## References

- `specs/020-agent-capability-first/research.md`
- `src/retrieval/macro/pairing.py`, `validator.py`
- `src/parsing/xbrl_facts.py`
