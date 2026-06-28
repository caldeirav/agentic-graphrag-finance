# Data Model: Agent Capability-First Numeric Synthesis

## StructuredAnswerPayload

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| metric_label | string | yes | Human-readable metric name (e.g., "Total debt") |
| value | string | yes | Numeric value as stated in source |
| unit | string | no | USD, shares, ratio, percent |
| fiscal_period | string | no | FY2025, Q1 2026, etc. |
| concept | string | no | XBRL concept if known |
| citation_chunk_ids | list[string] | yes | Evidence chunk ids supporting the claim |
| confidence | enum | yes | high \| medium \| low |
| abstain | boolean | yes | true if evidence insufficient |
| abstain_reason | string | no | Required when abstain=true |

## XbrlFactResolutionResult

| Field | Type | Description |
|-------|------|-------------|
| selected_chunk_ids | list[string] | Subset of input XBRL evidence |
| rationale | string | One sentence for trajectory |
| sufficient | boolean | false → synthesis should abstain |

## AgentState extensions

| Field | Type | Source |
|-------|------|--------|
| fiscal_period_labels_json | string | runner metadata `fiscal_period_labels` |

## Cohort file schema (`xbrl_numeric_cohort.json`)

Must validate as `Tier1CohortFile` (same as `tier1_cohort.json` from feature 019):

```json
{
  "schema_version": "1.0.0",
  "source_queue_path": "...",
  "source_queue_hash": "...",
  "exported_at": "ISO-8601",
  "item_ids": ["v2-financebench-0428", "..."],
  "entries": [{"item_id": "...", "priority_tier": 1, "priority_score": 0.0}]
}
```

Committed fixture: `specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json`

## Environment flags

| Variable | Effect |
|----------|--------|
| USE_MOCK_LLM=1 | Enable deterministic synthesis shortcuts |
| (default) | Structured + LLM path only; no template dumps |
