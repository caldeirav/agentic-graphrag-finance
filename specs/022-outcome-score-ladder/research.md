# Research: Outcome Score Ladder (022)

**Date**: 2026-06-24  
**Baseline run**: `reports/cohort-xbrl-022-debug` (after informal 022 binding/guards, commit `99e9d48`)

## Implementation (2026-06-24)

Phases A–E code shipped on branch `019-agent-failure-investigation`:

| Phase | Modules | Unit tests |
|-------|---------|------------|
| A | `ratio_pair_resolution.py`, ratio branch in `numeric_computation.py` | `test_ratio_pair_resolution.py`, `test_ratio_no_dollar_rate.py` |
| B | `point_fact_selection.py`, synthesis point path | `test_point_fact_selection.py` |
| C | `slice_expansion.py`, `runner._item_slice` | `test_slice_expansion.py` |
| D | `html_table_fallback.py`, synthesis HTML path | `test_html_table_fallback.py` |
| E | segment dimension in `xbrl_fact_catalog.py`, guard fix | `test_segment_catalog.py` |

**Operator pending**: cohort re-runs + `check_phase_gate.py` per phase (T018–T065).

## Cohort progression

| Metric | 020 | 021 | 022 |
|--------|-----|-----|-----|
| outcome_gt0 | 0/26 | 0/26 | **0/26** |
| mean VA | 0.0 | 0.0 | **0.0** |
| abstain-like | 20 | 21 | **18** |
| mean routing | 0.06 | 0.09 | **0.14** |
| mean retrieval | 0.08 | 0.16 | **0.21** |
| XOM cal-2025 evidence | 0 | 0 | **21/26** |

**Insight**: Upstream judge criteria improved; **outcome_score flat** because no answer within ±5% of GT.

## Blocker taxonomy (022)

| Bucket | Count | Fix phase |
|--------|-------|-----------|
| Abstention / macro fail | 19 | B, C, D |
| Wrong substantive (single-fact $) | 7 | A, B |
| Ratio GT (percent-like) | 14 | A |
| Segment GT | 2 | E |
| Issuer CAT | 3 | B, C |

## Key item traces (022)

| item_id | Issue | Phase |
|---------|-------|-------|
| 0548, 0667, 0666 | Rate/margin as `$` single fact | A |
| 0592 | OCI concept as payout | A |
| 0436 | Abstain; equity fact missing in catalog | B, D |
| 0495 | CAT; ~28% numeric error (wrong period) | B, C |
| 0600 | macro temporal_mismatch FY2024 | C |
| 0428 | Consolidated $34B vs segment GT $254B | E |

## Expected uplift (planning)

| Phase | outcome_gt0 (range) | cumulative |
|-------|---------------------|------------|
| A Ratio pipeline | +2–6 | 2–6 |
| B Point facts | +1–5 | 5–11 |
| C Benchmark/slice | +1–4 | 7–15 |
| D HTML fallback | +1–4 | 8–12+ |
| E Segment graph | +0–2 | 10–15+ |

## Design decisions

| Decision | Rationale |
|----------|-----------|
| Cohort gate after each phase | Outcome only moves with VA; need empirical proof per increment |
| Ratio before segment | Segment needs graph work; ratio unlocks 9 items faster |
| Expand slice in repro, not only validator | YoY items need FY2024 10-K in manifest |
| HTML fallback gated | Avoid chunk-dump regression (020 guard) |
| Benchmark accession updates optional | Agent rebind may suffice; data fix for MRR/audit |

## References

- `specs/021-xbrl-numeric-binding/research.md`
- `configs/judges/gemini_2_5_pro.yaml` (value_alignment rubric)
- `src/evaluation/judges/outcome_scoring.py`
