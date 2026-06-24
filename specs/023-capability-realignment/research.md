# Research: Capability Realignment (023)

**Date**: 2026-06-24  
**Baseline**: `reports/cohort-022-phase-e/graph-full/results.json`

## 022-E cohort autopsy

| Metric | 022-E |
|--------|-------|
| outcome_gt0 | **0/26** |
| mean VA | **0.0** |
| abstention-like | **19/26** |
| computed_numeric answers | **0/26** |
| synthesis_path in results | **0/26** (telemetry bug) |

### Answer path classification (operator script)

| Pattern | Count | Path |
|---------|-------|------|
| structured_abstain | 8 | computed → None → structured LLM abstain |
| llm_narrative / fail | ~10 | live_llm |
| structured_point (wrong) | 3 | structured LLM or bypassed point heuristic |
| macro_fail | 1 | 0600 temporal_mismatch |
| computed_numeric | **0** | Target path never won |

### Target item notes

| item_id | Observed answer | Issue |
|---------|-----------------|-------|
| 0548 | Structured abstain — missing revenue + earnings | Retrieval + fallthrough |
| 0666 | LLM “~20.0%” prose | live_llm; VA=0 |
| 0667 | LLM “cannot calculate” | live_llm |
| 0436 | Structured abstain | Catalog/HTML insufficient |
| 0495 | Q1 2026 wrong period | Wrong fact, not LLM skill |
| 0600 | macro temporal_mismatch | Macro + slice (022-C incomplete) |

## Constitution gap analysis

| 022 module | VII status | 023 action |
|------------|------------|------------|
| `ratio_pair_resolution.py` | Keyword router | Retire live; extend LLM resolution |
| `point_fact_selection.py` | Keyword router | Retire live; LLM resolution |
| `html_table_fallback.py` | Regex bypass | Defer; optional LLM table skill later |
| `xbrl_concept_guards` pre-filter | Undocumented exception | Post-validation only |
| `compute_numeric_answer` | Allowed (Python math) | Keep |
| `resolve_xbrl_facts` | VII skill | **Primary** selection |
| `slice_expansion` | Repro/eval OK | Keep |

## Design decisions

| Decision | Rationale | Rejected |
|----------|-----------|----------|
| Block numeric LLM fallthrough | 0666 proves LLM math ≠ VA | “Helpful” narrative fallback |
| LLM selects 2 facts for ratios | VII remediation #3 | Regex pair routing (022) |
| Retrieval enrichment before synthesis | 0548 lacks both facts in evidence | More catalog guards |
| Persist trajectory on all repro runs | Cannot gate what we cannot measure | defer_judge-only snapshot |
| Keep Python compute | Principle I grounding | LLM division in prose |

## Expected uplift (conservative)

| Milestone | outcome_gt0 | Depends on |
|-----------|-------------|------------|
| M1 Single path + telemetry | 0–2 | No fallthrough |
| M2 LLM pair + enrichment | 2–5 | 0548/0667 facts in evidence |
| M3 Post-validation + macro 0600 | 5–8 | FY2024 bind |

## References

- `.specify/memory/constitution.md` Principle VII
- `specs/020-agent-capability-first/spec.md`
- `specs/022-outcome-score-ladder/research.md`
- `reports/cohort-022-phase-e/`
