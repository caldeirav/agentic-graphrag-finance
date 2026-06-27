"""Load XBRL fact nodes from bound filings in the graph index (023 M3b)."""

from __future__ import annotations

import hashlib

from graph.accession import accession_from_node_id
from models.enums import EvidenceSourceType, GraphNodeType
from models.filing import FilingRef
from models.query import EvidenceChunk


def xbrl_node_to_evidence_chunk(node, accession: str) -> EvidenceChunk:
    excerpt = (node.source_ref or node.label or "").strip()
    return EvidenceChunk(
        chunk_node_id=node.node_id,
        excerpt=excerpt[:2000],
        content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
        citation_label=(node.label or "XBRL")[:80],
        source_type=EvidenceSourceType.XBRL,
        accession=accession,
        section_id=str((node.properties or {}).get("section_id", "XBRL")),
    )


def collect_filing_xbrl_chunks(
    graph_api,
    snapshot_id: str,
    filing_set: list[FilingRef],
) -> list[EvidenceChunk]:
    """All XBRL fact nodes for bound filing accessions (period filter applied later)."""
    if not graph_api or not snapshot_id or not filing_set:
        return []
    snap = graph_api.get_snapshot(snapshot_id)
    accessions = {f.accession for f in filing_set if f.accession}
    if not accessions:
        return []
    out: list[EvidenceChunk] = []
    seen: set[str] = set()
    for node in snap.nodes:
        if node.node_type != GraphNodeType.CHUNK_XBRL_FACT:
            continue
        accession = accession_from_node_id(node.node_id)
        if accession not in accessions:
            continue
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        out.append(xbrl_node_to_evidence_chunk(node, accession))
    return out


def merge_xbrl_evidence(
    evidence: list[EvidenceChunk],
    filing_chunks: list[EvidenceChunk],
) -> list[EvidenceChunk]:
    by_id = {c.chunk_node_id: c for c in evidence}
    for chunk in filing_chunks:
        by_id.setdefault(chunk.chunk_node_id, chunk)
    return list(by_id.values())
