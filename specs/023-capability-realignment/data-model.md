# Data Model: Capability Realignment (023)

## NumericSynthesisPolicy

| Field | Type | Description |
|-------|------|-------------|
| block_llm_fallback | bool | Default true for numeric metric types |
| allowed_paths | list[string] | `computed_numeric`, `numeric_abstain` |
| mock_only_modules | list[string] | Retired 022 heuristics |

## XbrlTaxonomyCatalog (v3, M4)

| Field | Type | Description |
|-------|------|-------------|
| schema_version | string | `3.0.0` |
| entries | list[XbrlFactCatalogEntryV2] | Period-filtered + taxonomy metadata |
| filing_accessions | list[string] | Bound filings in index |

## XbrlFactCatalogEntryV2 (extends v1)

| Field | Type | Description |
|-------|------|-------------|
| standard_label | string | From linkbase or concept role registry |
| metric_roles | list[string] | e.g. net_income, pretax_income, revenue |
| statement_role | string | income_statement / balance_sheet / … |
| calc_parents | list[string] | Calculation linkbase parents |
| calc_children | list[string] | Calculation linkbase children |
| accession | string | Filing accession for audit |

Contract: `contracts/xbrl-catalog-v3.schema.json`

## XbrlConceptMeta (parse/index, M4)

| Field | Type | Description |
|-------|------|-------------|
| concept | string | Local concept name |
| standard_label | string | Label linkbase |
| metric_roles | list[string] | Inferred from label text + roles |
| statement_role | string | From presentation linkbase |
| calc_parents / calc_children | list[string] | Calculation linkbase |

Stored on `ParsedDocument.xbrl_taxonomy_index` and graph `CHUNK_XBRL_FACT` node properties.

## RatioPairRoleAssignment (M4b)

| Field | Type | Description |
|-------|------|-------------|
| numerator | XbrlFactCatalogEntryV2 | Assigned by metric_roles, not list order |
| denominator | XbrlFactCatalogEntryV2 | Assigned by metric_roles |

Module: `ratio_entry_roles.py`; used in `validate_xbrl_resolution` and `compute_numeric_answer`.

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
