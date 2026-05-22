# Data Model: HTML Narrative Supplement & Intent Router (005)

**Feature**: 005 | **Date**: 2026-05-21

## Enumerations (`models/enums.py`)

| Enum | Values | Use |
|------|--------|-----|
| `EvidenceSourceType` | `XBRL`, `HTML` | Parse sections, graph nodes, citations |
| `QueryIntent` | `numeric`, `qualitative`, `hybrid` | Router output |
| `IntentSource` | `llm`, `keyword_fallback` | How intent was derived |
| `SourceBias` | `xbrl_primary`, `html_primary`, `blended` | Applied ranking policy |
| `RouterFallbackReason` | `llm_timeout`, `invalid_label`, `mock_llm`, `router_error` | When fallback used |
| `NarrativeSectionKind` | `business_description`, `risk_factors`, `md_and_a`, `other` | HTML parse labels |
| `HtmlNarrativeStatus` | `success`, `failed`, `skipped`, `not_attempted` | Per-filing ingest/parse |

## Extended: `SectionBlock` (`models/filing.py`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `source_type` | `EvidenceSourceType` | `XBRL` | HTML sections set `HTML` |
| `narrative_kind` | `NarrativeSectionKind \| None` | `None` | HTML only |

Existing fields unchanged: `section_id`, `title`, `level`, `text`, `parent_section_id`.

## Extended: `ParsedDocument` (`models/parsing.py`)

| Field | Type | Notes |
|-------|------|-------|
| `html_narrative_status` | `HtmlNarrativeStatus` | Per-filing HTML path outcome |
| `html_artifact_path` | `str` | Relative path under accession cache |

Validation: at least one `source_type=XBRL` section when XBRL parse succeeded; HTML sections optional.

## Extended: `GraphNode.properties`

| Key | Type | Values |
|-----|------|--------|
| `source_type` | str | `XBRL`, `HTML` |
| `narrative_kind` | str | optional section kind |

Set in `docling_graph_mapper` from `SectionBlock.source_type`.

## `IntentRouterTrace` (`models/query.py`)

| Field | Type | Required |
|-------|------|----------|
| `query_intent` | `QueryIntent` | yes |
| `intent_source` | `IntentSource` | yes |
| `source_bias_applied` | `SourceBias` | yes |
| `router_fallback_reason` | `RouterFallbackReason \| None` | when `intent_source=keyword_fallback` |
| `router_model_id` | `str` | when `intent_source=llm` |
| `router_raw_label` | `str` | optional |
| `router_latency_ms` | `int` | optional |
| `classified_at` | `datetime` | yes |

Mapping `query_intent` → `source_bias_applied`:

| query_intent | source_bias_applied |
|--------------|---------------------|
| `numeric` | `xbrl_primary` |
| `qualitative` | `html_primary` |
| `hybrid` | `blended` |

## Extended: `EvidenceChunk` (`models/query.py`)

| Field | Type | Required |
|-------|------|----------|
| `source_type` | `EvidenceSourceType` | yes (default from graph node) |
| `accession` | `str` | yes |
| `section_id` | `str` | optional |

## Extended: `TrajectoryRecord` (`models/query.py`)

| Field | Type | Notes |
|-------|------|-------|
| `intent_router` | `IntentRouterTrace \| None` | Canonical `query_intent` (FR-013) |
| `plan` | `MacroPlan \| None` | Unchanged; must not replace intent fields |

## Extended: `AgentState` (`retrieval/orchestration/state.py`)

| Key | Type |
|-----|------|
| `intent_trace` | `IntentRouterTrace` |

## Ingest manifest extensions (`CacheEntry` / manifest JSON)

| Field | Type |
|-------|------|
| `html_narrative_status` | `HtmlNarrativeStatus` |
| `html_artifact_role` | `inline_ixbrl \| filing_htm_fallback` |
| `html_artifact_relpath` | `str` |

## `SupplementaryHtmlArtifact` (logical entity)

| Field | Description |
|-------|-------------|
| `accession` | Paired XBRL accession |
| `resolved_path` | Path under `data/raw/sec_downloads/...` |
| `role` | Inline vs fallback |
| `content_hash` | SHA-256 of normalized HTML bytes |

## Relationships

```text
CacheEntry (XBRL complete)
    └── SupplementaryHtmlArtifact (optional path)
            └── html_narrative.parse → list[SectionBlock HTML]
                    └── merge → ParsedDocument (single JSON)
                            └── docling_graph_mapper → GraphNode (source_type)
                                    └── intent_router → IntentRouterTrace
                                            └── micro_extractor (biased rank)
                                                    └── EvidenceChunk (source_type)
                                                            └── TrajectoryRecord + MLflow
```
