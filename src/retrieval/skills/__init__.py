"""Agent skills: structured synthesis and XBRL fact resolution."""

from retrieval.skills.structured_answer import (
    StructuredAnswerPayload,
    is_chunk_dump_answer,
    render_structured_answer,
    synthesize_structured_answer,
)
from retrieval.skills.xbrl_fact_resolution import (
    XbrlFactResolutionResult,
    resolve_xbrl_facts,
)

__all__ = [
    "StructuredAnswerPayload",
    "XbrlFactResolutionResult",
    "is_chunk_dump_answer",
    "render_structured_answer",
    "resolve_xbrl_facts",
    "synthesize_structured_answer",
]
