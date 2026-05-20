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
