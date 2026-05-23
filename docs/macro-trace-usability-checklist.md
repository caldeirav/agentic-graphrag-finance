# Macro trace usability checklist (SC-005)

**Feature**: 008-autonomous-macro-routing  
**Success criterion**: [SC-005](../specs/008-autonomous-macro-routing/spec.md) — an analyst can identify why a filing set was chosen in **under 30 seconds** using trajectory or trace output alone.

**When to run**: After Phase 4 (US4) trajectory tasks land (T030–T032 minimum); required before feature sign-off (task T045).

**Not CI**: Manual timed review; record results in [usability-sc005.md](../specs/008-autonomous-macro-routing/checklists/usability-sc005.md).

## Prerequisites

- Materialized multi-filing corpus for the test ticker (e.g. AAPL per quickstart).
- `USE_MOCK_LLM=1` acceptable for binding-only checks; live LLM optional for realism.
- Console trace enabled: `--trace normal` (or `verbose` if fields missing at normal).

## Pass criteria (per query)

Within **30 seconds** of reading stderr trace (and optional MLflow `macro_binding.json`), the reviewer can answer:

1. **Which accessions** are active for this query?
2. **What comparison mode** applies (if any)?
3. **Why** — one-sentence rationale or explicit pre-bound / fail-closed reason?

**Pass** if all three are visible without opening meso/micro panels or re-running the query.

**Fail** if any answer requires digging into chunk evidence, re-parsing the query, or guessing from accession IDs alone.

## Procedure

1. Copy the five queries from [quickstart §5](../specs/008-autonomous-macro-routing/quickstart.md) (or the table in `usability-sc005.md`).
2. For each query, run:

   ```bash
   USE_MOCK_LLM=1 uv run agent-query ask --ticker AAPL --trace normal --query "<query>"
   ```

3. Start a timer when macro trace output appears; stop when you can state accessions, comparison mode, and rationale.
4. Record `time_s` and `pass`/`fail` in `checklists/usability-sc005.md`.
5. **Gate**: all 5 queries must **pass** (≤30s each). Any fail → improve macro trace renderer (T032) or trajectory fields (T031/T033) before sign-off.

## Representative queries (default set)

| # | Query | Expected macro signal |
|---|--------|------------------------|
| 1 | What was revenue in the prior quarter? | Single 10-Q; anchor prior quarter; rationale |
| 2 | Summarize risk factors in the latest annual report. | Single 10-K; latest annual |
| 3 | How did revenue change year over year? | Two accessions; YoY comparison mode |
| 4 | Compare this quarter to the previous quarter. | Two accessions; QoQ comparison mode |
| 5 | (Pre-bound) Same as #1 with explicit `--period` / anchor flags if quickstart defines one | `binding_source=cli` or pre-bound skip reason |

Adjust queries if quickstart §5 differs; keep five distinct paths (single-filing NL, annual, YoY, QoQ, CLI/pre-bound).

## Related artifacts

- Contract: [macro-trajectory.md](../specs/008-autonomous-macro-routing/contracts/macro-trajectory.md)
- Batch field audit (SC-003): `tests/integration/test_macro_trajectory_batch.py` (T029a)
- Record sheet: [usability-sc005.md](../specs/008-autonomous-macro-routing/checklists/usability-sc005.md)
