# Data Model: Outcome Score Ladder (022)

## RatioPairIntent (extends MetricIntent)

| Field | Type | Description |
|-------|------|-------------|
| numerator_concept_family | string | `income`, `tax`, `dividend`, … |
| denominator_concept_family | string | `revenue`, `pretax_income`, `net_income`, … |
| output_unit | string | Always `percent` for ratio/margin/rate |
| min_pairs_required | int | Default 2 |

## RatioPairResolution

| Field | Type | Description |
|-------|------|-------------|
| numerator_entry | XbrlFactCatalogEntry | |
| denominator_entry | XbrlFactCatalogEntry | |
| sufficient | bool | Both pass guards + period match |
| abstain_reason | string | When insufficient |

## PointFactSelection

| Field | Type | Description |
|-------|------|-------------|
| concept | string | Primary XBRL concept chosen |
| period_end | string | ISO date |
| value_normalized | float | Parsed numeric |
| scale | string | `units`, `millions`, `billions` |
| issuer_ticker | string | XOM, CAT, … |
| accession | string | Bound filing |

## SliceExpansionRequest

| Field | Type | Description |
|-------|------|-------------|
| seed_accessions | list[string] | From expected_bindings |
| temporal_intent | TemporalScopeIntent | |
| comparison_years | list[int] | e.g. [2024, 2025] |
| expanded_accessions | list[string] | Output for subgraph loader |

## HtmlTableExtraction

| Field | Type | Description |
|-------|------|-------------|
| table_hint | string | `equity_rollforward`, `cash_flow`, … |
| row_label | string | Matched row |
| column_period | string | FY2025, etc. |
| value_display | string | Parsed cell |
| chunk_id | string | Source HTML chunk |
| confidence | string | high / medium / low |

## SegmentDimensionEntry (Phase E)

| Field | Type | Description |
|-------|------|-------------|
| segment_name | string | e.g. Energy Products |
| concept | string | Revenue concept |
| dimension_axis | string | XBRL axis name |
| member | string | Segment member id |

## CohortPhaseGate (validation artifact)

| Field | Type | Description |
|-------|------|-------------|
| phase | string | A, B, C, D, E |
| report_dir | string | e.g. reports/cohort-022-phase-a |
| outcome_gt0 | int | |
| mean_outcome | float | |
| target_floor | int | From SC-A…SC-E |
| passed | bool | |

## AgentState extensions (optional JSON)

| Field | Source |
|-------|--------|
| ratio_pair_resolution_json | ratio pipeline |
| html_fallback_used | bool |
| slice_expansion_accessions_json | repro runner |
