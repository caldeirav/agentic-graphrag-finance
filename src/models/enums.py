from enum import StrEnum


class GraphNodeType(StrEnum):
    DOCUMENT = "DOCUMENT"
    SECTION = "SECTION"
    CHUNK_TABLE = "CHUNK_TABLE"
    CHUNK_ROW = "CHUNK_ROW"
    CHUNK_PARAGRAPH = "CHUNK_PARAGRAPH"
    CHUNK_XBRL_FACT = "CHUNK_XBRL_FACT"


class GraphEdgeType(StrEnum):
    CONTAINS = "CONTAINS"
    NEXT = "NEXT"
    FOOTNOTE_OF = "FOOTNOTE_OF"
    REFERENCES = "REFERENCES"
    TEMPORAL_TRANSITION = "TEMPORAL_TRANSITION"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"


class QueryStatus(StrEnum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ERROR = "ERROR"


class Sufficiency(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class OperationClass(StrEnum):
    QUALITATIVE = "QUALITATIVE"
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    COMPOSITIONAL = "COMPOSITIONAL"


class ComparisonMode(StrEnum):
    YOY = "YoY"
    QOQ = "QoQ"
    SEQUENTIAL = "sequential"


class EvidenceSourceType(StrEnum):
    XBRL = "XBRL"
    HTML = "HTML"


class QueryIntent(StrEnum):
    NUMERIC = "numeric"
    QUALITATIVE = "qualitative"
    HYBRID = "hybrid"


class IntentSource(StrEnum):
    LLM = "llm"
    KEYWORD_FALLBACK = "keyword_fallback"


class SourceBias(StrEnum):
    XBRL_PRIMARY = "xbrl_primary"
    HTML_PRIMARY = "html_primary"
    BLENDED = "blended"


class RouterFallbackReason(StrEnum):
    LLM_TIMEOUT = "llm_timeout"
    INVALID_LABEL = "invalid_label"
    MOCK_LLM = "mock_llm"
    ROUTER_ERROR = "router_error"


class NarrativeSectionKind(StrEnum):
    BUSINESS_DESCRIPTION = "business_description"
    RISK_FACTORS = "risk_factors"
    MD_AND_A = "md_and_a"
    OTHER = "other"


class HtmlNarrativeStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_ATTEMPTED = "not_attempted"
