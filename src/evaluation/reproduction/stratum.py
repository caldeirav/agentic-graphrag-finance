"""Evidence stratum assignment for stratified ablation export (015)."""

from __future__ import annotations

from typing import Literal

ChunkKind = Literal["html", "xbrl"]
EvidenceStratum = Literal["html", "xbrl", "mixed", "unknown"]


def classify_chunk_id(chunk_id: str) -> ChunkKind:
    """Classify a relevance chunk id as HTML narrative or XBRL fact."""
    lowered = chunk_id.lower()
    if "-html-" in lowered or lowered.startswith("html-"):
        return "html"
    if "xbrl" in lowered:
        return "xbrl"
    return "html"


def assign_primary_evidence_source(relevant_chunk_ids: list[str]) -> EvidenceStratum:
    """Uniform stratum rule: all html → html; all xbrl → xbrl; both → mixed; empty → unknown."""
    if not relevant_chunk_ids:
        return "unknown"
    kinds = {classify_chunk_id(cid) for cid in relevant_chunk_ids}
    if kinds == {"html"}:
        return "html"
    if kinds == {"xbrl"}:
        return "xbrl"
    return "mixed"
