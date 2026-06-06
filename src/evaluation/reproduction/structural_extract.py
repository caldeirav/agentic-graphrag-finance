"""Extract structural audit inputs from trajectory snapshots (015)."""

from __future__ import annotations

import re

from graph.accession import accession_from_node_id
from tracing.trajectory_export import normalize_trajectory_state

_ACCESSION_IN_DOC_ID = re.compile(r"doc-(\d{10}-\d{2}-\d{6})-")


def _accession_from_chunk_id(node_id: str) -> str | None:
    match = _ACCESSION_IN_DOC_ID.match(node_id)
    if match:
        return match.group(1)
    acc = accession_from_node_id(node_id)
    return acc or None


def extract_used_accessions(trajectory_snapshot: dict | None) -> set[str]:
    """Accessions from filing route and cited / evidence chunk node ids."""
    if not trajectory_snapshot:
        return set()
    state = normalize_trajectory_state(trajectory_snapshot)
    used: set[str] = set()

    for filing in state.get("filing_set") or []:
        if isinstance(filing, dict):
            acc = filing.get("accession")
            if acc:
                used.add(str(acc))
        elif hasattr(filing, "accession"):
            used.add(str(filing.accession))

    for route in state.get("document_route") or []:
        if isinstance(route, dict) and route.get("accession"):
            used.add(str(route["accession"]))

    for key in ("evidence_chunks", "evidence"):
        for entry in state.get(key) or []:
            node_id = ""
            if isinstance(entry, dict):
                node_id = str(entry.get("chunk_node_id") or entry.get("node_id") or "")
            elif hasattr(entry, "chunk_node_id"):
                node_id = str(entry.chunk_node_id)
            if node_id:
                acc = _accession_from_chunk_id(node_id)
                if acc:
                    used.add(acc)

    for hop in state.get("graph_traversal") or []:
        if isinstance(hop, dict):
            node_id = str(hop.get("node_id") or hop.get("to_node_id") or "")
        else:
            node_id = str(getattr(hop, "node_id", "") or getattr(hop, "to_node_id", ""))
        if node_id:
            acc = _accession_from_chunk_id(node_id)
            if acc:
                used.add(acc)

    return used


def extract_visited_paths(trajectory_snapshot: dict | None) -> set[str]:
    """Section / graph node ids visited during retrieval."""
    if not trajectory_snapshot:
        return set()
    state = normalize_trajectory_state(trajectory_snapshot)
    paths: set[str] = set()

    for hop in state.get("graph_traversal") or []:
        if isinstance(hop, dict):
            for key in ("node_id", "to_node_id", "from_node_id"):
                val = hop.get(key)
                if val:
                    paths.add(str(val))
        else:
            for attr in ("node_id", "to_node_id", "from_node_id"):
                val = getattr(hop, attr, None)
                if val:
                    paths.add(str(val))

    for key in ("evidence_chunks", "evidence"):
        for entry in state.get(key) or []:
            if isinstance(entry, dict):
                for field in ("chunk_node_id", "node_id", "section_id"):
                    val = entry.get(field)
                    if val:
                        paths.add(str(val))
            else:
                for attr in ("chunk_node_id", "node_id", "section_id"):
                    val = getattr(entry, attr, None)
                    if val:
                        paths.add(str(val))

    return paths


def build_structural_inputs(
    results: list,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Map item_id → used accessions and visited paths from benchmark results."""
    used_by_item: dict[str, set[str]] = {}
    paths_by_item: dict[str, set[str]] = {}
    for row in results:
        snap = row.trajectory_snapshot if hasattr(row, "trajectory_snapshot") else None
        used_by_item[row.item_id] = extract_used_accessions(snap)
        paths_by_item[row.item_id] = extract_visited_paths(snap)
    return used_by_item, paths_by_item
