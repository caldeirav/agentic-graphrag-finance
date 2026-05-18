"""Shared Pydantic data contracts."""

from models.enums import (
    GraphEdgeType,
    GraphNodeType,
    OperationClass,
    QueryStatus,
    Sufficiency,
)
from models.filing import CellSpan, FilingRef, FootnoteBlock, SectionBlock, TableBlock
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot
from models.parsing import ParsedDocument
from models.query import (
    AnswerPackage,
    EvidenceChunk,
    GraphVisit,
    MacroPlan,
    SectionCandidate,
    TemporalScope,
    TrajectoryRecord,
)
from models.evaluation import BenchmarkItem, BenchmarkResult, EvaluationRun, GroundTruth, JudgeVerdict

__all__ = [
    "GraphEdgeType",
    "GraphNodeType",
    "OperationClass",
    "QueryStatus",
    "Sufficiency",
    "FilingRef",
    "CellSpan",
    "SectionBlock",
    "TableBlock",
    "FootnoteBlock",
    "ParsedDocument",
    "GraphNode",
    "GraphEdge",
    "GraphManifest",
    "GraphSnapshot",
    "MacroPlan",
    "TemporalScope",
    "SectionCandidate",
    "EvidenceChunk",
    "AnswerPackage",
    "GraphVisit",
    "TrajectoryRecord",
    "GroundTruth",
    "BenchmarkItem",
    "BenchmarkResult",
    "JudgeVerdict",
    "EvaluationRun",
]
