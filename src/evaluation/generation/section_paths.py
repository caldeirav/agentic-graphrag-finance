"""Resolve Gemini section paths against corpus graph_node_index entries."""

from __future__ import annotations

import re


def normalize_section_key(value: str) -> str:
    """Collapse 'Item 1A.' / 'Item1A' / 'item-1a' to comparable token."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def parse_section_path(section_path: str) -> tuple[str, str]:
    if "/" in section_path:
        accession, tail = section_path.split("/", 1)
        return accession.strip(), tail.strip()
    return "", section_path.strip()


def item_number_key(value: str) -> str | None:
    match = re.search(r"item(\d+[a-z]?)", value.lower())
    if not match:
        return None
    return f"item{match.group(1)}"


def _accession_in_path(accession: str, graph_path: str) -> bool:
    if not accession:
        return True
    compact = accession.replace("-", "")
    return accession in graph_path or compact in graph_path.replace("-", "")


def _issuer_key(accession: str) -> str:
    parts = accession.split("-")
    return parts[0] if parts else accession


def resolve_section_path(
    path: str,
    graph_paths: set[str],
    *,
    snapshot_accessions: set[str],
) -> str | None:
    """Return canonical graph index path for *path*, or None if unresolvable."""
    if path in graph_paths:
        return path

    accession, tail = parse_section_path(path)
    tail_key = normalize_section_key(tail)
    item_key = item_number_key(tail_key)
    if not tail_key:
        return None

    best: str | None = None
    best_score = -1

    for graph_path in graph_paths:
        graph_accession, graph_tail = parse_section_path(graph_path)
        graph_tail_key = normalize_section_key(graph_tail)
        graph_item_key = item_number_key(graph_tail_key)

        accession_ok = False
        if accession and graph_accession:
            if accession == graph_accession:
                accession_ok = True
            elif _accession_in_path(accession, graph_path):
                accession_ok = True
            elif (
                accession in snapshot_accessions
                and graph_accession in snapshot_accessions
                and _issuer_key(accession) == _issuer_key(graph_accession)
            ):
                accession_ok = True
        elif graph_accession in snapshot_accessions:
            accession_ok = True
        elif accession in snapshot_accessions and not graph_accession:
            accession_ok = True

        if not accession_ok:
            continue

        section_ok = False
        if item_key and graph_item_key and item_key == graph_item_key:
            section_ok = True
        elif tail_key == graph_tail_key:
            section_ok = True
        elif tail_key.startswith(graph_tail_key) or graph_tail_key.startswith(tail_key):
            section_ok = True

        if not section_ok:
            continue

        score = 0
        if accession and graph_accession == accession:
            score += 4
        elif _accession_in_path(accession, graph_path):
            score += 2
        if tail_key == graph_tail_key:
            score += 3
        elif item_key and graph_item_key == item_key:
            score += 2
        score += min(len(graph_tail_key), len(tail_key))

        if score > best_score:
            best_score = score
            best = graph_path

    return best


def resolve_section_paths(
    paths: list[str],
    graph_paths: set[str],
    *,
    snapshot_accessions: set[str],
) -> tuple[list[str], list[str]]:
    """Resolve each path; return (canonical_paths, unresolved_paths)."""
    canonical: list[str] = []
    unresolved: list[str] = []
    for path in paths:
        resolved = resolve_section_path(
            path,
            graph_paths,
            snapshot_accessions=snapshot_accessions,
        )
        if resolved is None:
            unresolved.append(path)
        else:
            canonical.append(resolved)
    return canonical, unresolved
