"""Agent skills: structured synthesis, temporal binding, XBRL resolution, computation."""

from retrieval.skills.metric_intent import MetricIntent, classify_metric_intent
from retrieval.skills.numeric_computation import compute_numeric_answer
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
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry, build_xbrl_fact_catalog
from retrieval.skills.xbrl_fact_resolution import (
    XbrlFactResolutionResult,
    resolve_xbrl_facts,
    resolve_xbrl_facts_from_catalog,
)

__all__ = [
    "MetricIntent",
    "StructuredAnswerPayload",
    "TemporalScopeIntent",
    "XbrlFactCatalogEntry",
    "XbrlFactResolutionResult",
    "align_filings_to_intent",
    "apply_intent_to_proposal",
    "build_xbrl_fact_catalog",
    "classify_metric_intent",
    "compute_numeric_answer",
    "concept_passes_guard",
    "infer_temporal_scope_intent",
    "is_chunk_dump_answer",
    "normalize_fiscal_period_labels",
    "query_concept_family",
    "render_structured_answer",
    "resolve_filings_to_intent",
    "resolve_xbrl_facts",
    "resolve_xbrl_facts_from_catalog",
    "synthesize_structured_answer",
    "xbrl_period_matches_intent",
]
