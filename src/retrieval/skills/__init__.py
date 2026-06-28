"""Agent skills: structured synthesis, temporal binding, XBRL resolution, computation."""

from retrieval.skills.metric_intent import MetricIntent, classify_metric_intent, heuristic_metric_intent
from retrieval.skills.numeric_computation import compute_numeric_answer, format_numeric_display
from retrieval.skills.point_fact_selection import PointFactSelection, select_point_fact
from retrieval.skills.ratio_pair_resolution import (
    RatioPairIntent,
    RatioPairResolution,
    infer_ratio_pair_intent,
    ratio_pair_to_resolution,
    resolve_ratio_pair,
)
from retrieval.skills.structured_answer import (
    StructuredAnswerPayload,
    is_chunk_dump_answer,
    render_structured_answer,
    synthesize_structured_answer,
)
from retrieval.skills.temporal_scope import (
    TemporalScopeIntent,
    align_filings_to_intent,
    apply_intent_to_proposal,
    infer_temporal_scope_intent,
    normalize_fiscal_period_labels,
    resolve_filings_to_intent,
    xbrl_period_matches_intent,
)
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family
from retrieval.skills.xbrl_concept_roles import ConceptRoleRule, register_concept_role_rules
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry, build_xbrl_fact_catalog
from retrieval.skills.xbrl_resolution_validate import ValidatedXbrlResolution, validate_xbrl_resolution
from retrieval.skills.xbrl_taxonomy_catalog import (
    CATALOG_SCHEMA_VERSION,
    XbrlFactCatalogEntryV2,
    XbrlTaxonomyCatalog,
    build_taxonomy_catalog,
    catalog_entries_for_resolution,
    enrich_catalog_entry,
    rank_entries_by_metric_role,
)
from retrieval.skills.xbrl_fact_resolution import (
    XbrlFactResolutionResult,
    resolve_xbrl_facts,
    resolve_xbrl_facts_from_catalog,
)

__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "ConceptRoleRule",
    "MetricIntent",
    "PointFactSelection",
    "RatioPairIntent",
    "RatioPairResolution",
    "StructuredAnswerPayload",
    "TemporalScopeIntent",
    "ValidatedXbrlResolution",
    "XbrlFactCatalogEntry",
    "XbrlFactCatalogEntryV2",
    "XbrlFactResolutionResult",
    "XbrlTaxonomyCatalog",
    "align_filings_to_intent",
    "apply_intent_to_proposal",
    "build_taxonomy_catalog",
    "build_xbrl_fact_catalog",
    "catalog_entries_for_resolution",
    "enrich_catalog_entry",
    "classify_metric_intent",
    "compute_numeric_answer",
    "concept_passes_guard",
    "format_numeric_display",
    "heuristic_metric_intent",
    "infer_ratio_pair_intent",
    "infer_temporal_scope_intent",
    "is_chunk_dump_answer",
    "normalize_fiscal_period_labels",
    "query_concept_family",
    "rank_entries_by_metric_role",
    "register_concept_role_rules",
    "ratio_pair_to_resolution",
    "render_structured_answer",
    "resolve_ratio_pair",
    "resolve_filings_to_intent",
    "resolve_xbrl_facts",
    "resolve_xbrl_facts_from_catalog",
    "select_point_fact",
    "synthesize_structured_answer",
    "validate_xbrl_resolution",
    "xbrl_period_matches_intent",
]
