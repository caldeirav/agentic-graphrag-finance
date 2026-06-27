"""Load XBRL fact nodes from bound filings in the graph index (023 M3b)."""

from __future__ import annotations

import hashlib

from graph.accession import accession_from_node_id
from models.enums import EvidenceSourceType, GraphNodeType
from models.filing import FilingRef
from models.query import EvidenceChunk
from parsing.xbrl_taxonomy_index import XbrlConceptMeta, build_taxonomy_index, taxonomy_meta_from_properties


def _package_root_for_accession(accession: str) -> Path | None:
    from ingestion.settings import get_settings, is_fixture_ingestion

    root = (
        get_settings().fixture_downloads_root
        if is_fixture_ingestion()
        else get_settings().sec_downloads_root
    )
    if not root.is_dir():
        return None
    for ticker_dir in root.iterdir():
        if not ticker_dir.is_dir():
            continue
        candidate = ticker_dir / accession
        if candidate.is_dir():
            return candidate
    return None


def load_filing_taxonomy_from_packages(
    filing_set: list[FilingRef],
) -> dict[str, XbrlConceptMeta]:
    """Load linkbase metadata from local SEC packages when graph nodes lack taxonomy props."""
    from parsing.docling_xbrl import find_taxonomy_dir

    lookup: dict[str, XbrlConceptMeta] = {}
    for filing in filing_set:
        accession = filing.accession or ""
        if not accession:
            continue
        package_root = _package_root_for_accession(accession)
        if package_root is None:
            continue
        instance_candidates = sorted(package_root.glob("*_htm.xml"))
        if not instance_candidates:
            instance_candidates = [
                p
                for p in package_root.glob("*.xml")
                if not p.name.lower().endswith(("_lab.xml", "_pre.xml", "_cal.xml", "_def.xml"))
            ]
        if not instance_candidates:
            continue
        taxonomy_dir = find_taxonomy_dir(package_root, instance_candidates[0])
        lookup.update(build_taxonomy_index(taxonomy_dir))
    return lookup


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


def collect_filing_xbrl_taxonomy_lookup(
    graph_api,
    snapshot_id: str,
    filing_set: list[FilingRef],
) -> dict[str, XbrlConceptMeta]:
    """Concept → taxonomy metadata from graph XBRL fact node properties."""
    if not graph_api or not snapshot_id or not filing_set:
        return {}
    snap = graph_api.get_snapshot(snapshot_id)
    accessions = {f.accession for f in filing_set if f.accession}
    if not accessions:
        return {}
    lookup: dict[str, XbrlConceptMeta] = {}
    for node in snap.nodes:
        if node.node_type != GraphNodeType.CHUNK_XBRL_FACT:
            continue
        accession = accession_from_node_id(node.node_id)
        if accession not in accessions:
            continue
        meta = taxonomy_meta_from_properties(node.properties or {})
        if not meta:
            continue
        concept = meta.concept or str((node.properties or {}).get("xbrl_concept") or "")
        if concept:
            lookup[concept] = meta
    return lookup


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
