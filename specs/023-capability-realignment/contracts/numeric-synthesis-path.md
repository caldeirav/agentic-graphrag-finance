# Contract: Numeric Synthesis Path Policy (023)

## Live numeric path (USE_MOCK_LLM unset)

```text
enrich_numeric_evidence?
  → build_xbrl_fact_catalog (period/temporal only)
  → classify_metric_intent (LLM)
  → resolve_xbrl_facts (LLM; 1–2 facts)
  → validate_xbrl_resolution (deterministic post-guard)
  → compute_numeric_answer (Python)
  → render OR numeric_abstain
```

## Forbidden transitions

| From | To | Condition |
|------|-----|-----------|
| numeric metric intent | `structured_llm` | **BLOCKED** |
| numeric metric intent | `live_llm` | **BLOCKED** |
| numeric metric intent | `ratio_pair_resolution` | **BLOCKED** (022 heuristic) |
| numeric metric intent | `point_fact_selection` | **BLOCKED** |
| numeric metric intent | `html_table_fallback` | **BLOCKED** (live) |

## Allowed synthesis_path values

| Value | Meaning |
|-------|---------|
| `computed_numeric` | Structured answer emitted |
| `numeric_abstain` | Insufficient facts; no LLM fallback |
| `template` / `numeric_xbrl_deterministic` | `USE_MOCK_LLM=1` only |

## Trajectory fields

| Field | Required |
|-------|----------|
| `synthesis_path` | Yes (all repro runs) |
| `metric_intent_json` | When numeric |
| `xbrl_resolution_json` | When resolution ran |
| `evidence_enrichment_json` | When enrichment added chunks |

## Judge interaction

- Abstain uses `QueryStatus.INSUFFICIENT_EVIDENCE`
- No change to VA rubric or judge model
