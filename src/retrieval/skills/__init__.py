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
)
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
    "infer_temporal_scope_intent",
    "is_chunk_dump_answer",
    "render_structured_answer",
    "resolve_xbrl_facts",
    "resolve_xbrl_facts_from_catalog",
    "synthesize_structured_answer",
]
