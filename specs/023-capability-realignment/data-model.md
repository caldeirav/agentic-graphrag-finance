# Data Model: Capability Realignment (023)

## NumericSynthesisPolicy

| Field | Type | Description |
|-------|------|-------------|
| block_llm_fallback | bool | Default true for numeric metric types |
| allowed_paths | list[string] | `computed_numeric`, `numeric_abstain` |
| mock_only_modules | list[string] | Retired 022 heuristics |

## XbrlResolutionRequest (extends 021)

| Field | Type | Description |
|-------|------|-------------|
| metric_intent | MetricIntent | point / ratio / delta / percent_change |
| catalog | list[XbrlFactCatalogEntry] | Full period-filtered catalog |
| forbidden_concept_patterns | list[string] | Prompt + post-validator hints |
| min_facts_required | int | 1 or 2 |
| temporal_intent | TemporalScopeIntent | |

## XbrlResolutionResult (extends 020)

| Field | Type | Description |
|-------|------|-------------|
| selected_chunk_ids | list[string] | 1 or 2 ids |
| selected_concepts | list[string] | Audit |
| sufficient | bool | |
| abstain_reason | string | |
| validation_rejections | list[string] | Post-guard failures |

## EvidenceEnrichmentRecord

| Field | Type | Description |
|-------|------|-------------|
| item_id | string | |
| missing_families | list[string] | e.g. revenue, net_income |
| added_chunk_ids | list[string] | |
| source_accession | string | |

## TrajectorySnapshotFix

| Field | Type | Description |
|-------|------|-------------|
| synthesis_path | string | Always set on BenchmarkResult |
| metric_intent_json | string | Optional |
| xbrl_resolution_json | string | Replaces ratio_pair_resolution_json |

## CohortPathAudit

| Field | Type | Description |
|-------|------|-------------|
| item_id | string | |
| synthesis_path | string | |
| path_class | enum | computed_numeric, numeric_abstain, live_llm, structured_llm, macro_fail |
| outcome_score | float | |
