# Data Model: XBRL Numeric Binding & Computation (021)

## TemporalScopeIntent

| Field | Type | Description |
|-------|------|-------------|
| anchor | string | `latest_annual`, `latest_quarter`, `prior_quarter`, null |
| target_fiscal_year | int \| null | e.g. 2025 from query or FY2025 label |
| form_preference | string | `10-K`, `10-Q`, or empty |
| comparison_mode | string \| null | `yoy`, `qoq`, null |
| period_labels | list[string] | e.g. `["FY2025"]` from benchmark metadata |
| rationale | string | Trace / debug |

## XbrlFactCatalogEntry

| Field | Type | Description |
|-------|------|-------------|
| chunk_id | string | Evidence chunk node id |
| concept | string | XBRL concept name |
| value_raw | string | Parsed numeric string |
| value_display | string | Human-readable ($X billion) |
| period_start | string | ISO date or empty |
| period_end | string | ISO date |
| is_annual | bool | Jan–Dec or ~365d heuristic |
| concept_family | string | revenue, equity, assets, cash, income, … |
| segment_hint | string \| null | Segment name if detected in excerpt |
| matches_query | bool | From `xbrl_concept_matches_query` |

## MetricIntent

| Field | Type | Enum |
|-------|------|------|
| metric_type | string | `point`, `delta`, `ratio`, `percent_change` |
| metric_label | string | Human label |
| required_concepts | list[string] | Hint for resolution |
| periods_needed | int | 1 or 2 |
| formula | string | e.g. `(a-b)/b*100` |

## StructuredAnswerPayload v2 (extends 020)

Additional fields:

| Field | Type | Description |
|-------|------|-------------|
| metric_type | string | Same as MetricIntent |
| inputs | list[object] | `{concept, period_end, value, chunk_id}` |
| formula | string | Declared computation |
| computed_value | string | Final numeric answer string |

## Trace / AgentState extensions

| Field | Source |
|-------|--------|
| temporal_scope_intent_json | temporal_scope skill |
| metric_intent_json | metric_intent skill |
| xbrl_resolution_rationale | existing + catalog summary |

## Environment

| Variable | Effect |
|----------|--------|
| USE_MOCK_LLM=1 | Deterministic numeric correctors allowed (CI) |
