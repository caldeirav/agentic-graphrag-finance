# SC-005 Usability Record: Macro Trace (30s gate)

**Purpose**: Record timed manual review for [SC-005](../spec.md) per [docs/macro-trace-usability-checklist.md](../../../docs/macro-trace-usability-checklist.md)  
**Task**: T045  
**Feature**: 008-autonomous-macro-routing

## Review metadata

| Field | Value |
|-------|--------|
| Reviewer | |
| Date | |
| Branch / commit | |
| Ticker | AAPL |
| Trace level | `--trace normal` |
| `USE_MOCK_LLM` | yes / no |

## Results (5 queries, each ≤30s)

| # | Query | Accessions visible? | Comparison mode visible? | Rationale visible? | time_s | Pass |
|---|--------|---------------------|-------------------------|-------------------|--------|------|
| 1 | What was revenue in the prior quarter? | | | | | |
| 2 | Summarize risk factors in the latest annual report. | | | | | |
| 3 | How did revenue change year over year? | | | | | |
| 4 | Compare this quarter to the previous quarter. | | | | | |
| 5 | _(CLI / pre-bound scenario from quickstart §5)_ | | | | | |

**Pass column**: `yes` if all three visibility checks met within 30s; otherwise `no`.

## Gate

- [ ] All 5 rows **Pass = yes**
- [ ] No query required meso/micro or chunk text to infer filing set
- [ ] Failures documented with trace snippet or screenshot path below

## Failure notes (if any)

_Query #, what was missing, follow-up task (e.g. T032):_

---

## Sign-off

- [ ] SC-005 satisfied — ready for feature completion (with T043 quickstart)
- [ ] SC-005 not satisfied — block until macro trace / trajectory fields updated
