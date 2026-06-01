"""Graph-grounded relevance label materialization (012)."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from evaluation.generation.item_validator import load_graph_paths
from evaluation.generation.section_paths import (
    item_number_key,
    normalize_section_key,
    parse_section_path,
    resolve_section_paths,
)
from evaluation.reproduction.manifest import sha256_text
from evaluation.reproduction.snapshot_loader import load_bundle_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphNode, GraphSnapshot
from models.reproduction import RelevanceFailure, RelevanceLabelSet

EVIDENCE_CHUNK_TYPES = frozenset(
    {
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
    }
)

RESOLVABLE_NODE_TYPES = frozenset(
    {
        GraphNodeType.SECTION,
        GraphNodeType.DOCUMENT,
    }
)


def _canonical_labels_payload(labels_by_item_id: dict[str, list[str]]) -> str:
    ordered = {
        k: sorted(labels_by_item_id[k])
        for k in sorted(labels_by_item_id)
    }
    return json.dumps({"labels_by_item_id": ordered}, sort_keys=True, separators=(",", ":"))


def compute_labels_hash(labels_by_item_id: dict[str, list[str]]) -> str:
    return sha256_text(_canonical_labels_payload(labels_by_item_id))


def _normalize_section_key(value: str) -> str:
    """Collapse 'Item 1A.' / 'Item1A' / 'item-1a' to comparable token."""
    return normalize_section_key(value)


def _parse_section_path(section_path: str) -> tuple[str, str]:
    return parse_section_path(section_path)


def _accession_matches(node: GraphNode, accession: str) -> bool:
    if not accession:
        return True
    node_key = node.node_id.replace("-", "")
    acc_key = accession.replace("-", "")
    return accession in node.node_id or acc_key in node_key


def _section_keys_for_node(node: GraphNode) -> set[str]:
    props = node.properties or {}
    keys = {
        _normalize_section_key(node.label or ""),
        _normalize_section_key(str(props.get("section_slug", ""))),
    }
    item_number = props.get("item_number")
    if item_number:
        keys.add(_normalize_section_key(f"Item {item_number}"))
        keys.add(_normalize_section_key(f"Item{item_number}"))
    return {k for k in keys if k}


def _section_matches(node: GraphNode, *, tail: str, tail_key: str, item_key: str | None) -> bool:
    node_label = node.label or ""
    node_label_key = _normalize_section_key(node_label)
    node_keys = _section_keys_for_node(node)

    if tail and tail in node_label:
        return True
    if tail_key and node_label_key and (
        tail_key == node_label_key
        or tail_key.startswith(node_label_key)
        or node_label_key.startswith(tail_key)
    ):
        return True
    if item_key and item_key in node_keys:
        return True
    if item_key and any(
        key.startswith("item") and (key.startswith(item_key) or item_key.startswith(key))
        for key in node_keys
    ):
        return True
    return bool(tail_key and tail_key in node_keys)


def _section_node_ids(snapshot: GraphSnapshot, section_path: str) -> list[str]:
    accession, tail = _parse_section_path(section_path)
    tail_key = _normalize_section_key(tail)
    item_key = item_number_key(tail_key)
    filing_accessions = {ref.accession for ref in snapshot.manifest.filing_refs}
    candidates: list[tuple[int, str]] = []

    for node in snapshot.nodes:
        if node.node_type not in RESOLVABLE_NODE_TYPES:
            continue
        if not _section_matches(node, tail=tail, tail_key=tail_key, item_key=item_key):
            continue
        if node.node_id == section_path or node.properties.get("section_path") == section_path:
            candidates.append((200, node.node_id))
            continue

        score = 0
        if accession and _accession_matches(node, accession):
            score += 100
        elif accession and accession in filing_accessions:
            score += 10
        elif not accession:
            score += 5
        else:
            continue

        node_label_key = _normalize_section_key(node.label or "")
        if tail_key and tail_key == node_label_key:
            score += 20
        elif item_key and item_key in _section_keys_for_node(node):
            score += 15
        elif tail and tail in (node.label or ""):
            score += 12
        else:
            score += 5
        candidates.append((score, node.node_id))

    if not candidates and section_path in {n.node_id for n in snapshot.nodes}:
        return [section_path]
    if not candidates:
        return []
    best = max(score for score, _ in candidates)
    return sorted({node_id for score, node_id in candidates if score == best})


def collect_chunks_under_section(
    snapshot: GraphSnapshot,
    section_node_id: str,
) -> list[str]:
    node_by_id = {n.node_id: n for n in snapshot.nodes}
    out: set[str] = set()
    queue: deque[str] = deque([section_node_id])
    visited: set[str] = set()

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        node = node_by_id.get(current)
        if node is not None and node.node_type in EVIDENCE_CHUNK_TYPES:
            out.add(current)
        for edge in snapshot.edges:
            if edge.edge_type != GraphEdgeType.CONTAINS:
                continue
            if edge.source_id == current and edge.target_id not in visited:
                queue.append(edge.target_id)

    return sorted(out)


def resolve_item_chunk_ids(
    snapshot: GraphSnapshot,
    section_paths: list[str],
) -> tuple[list[str], list[str]]:
    unresolved: list[str] = []
    chunks: set[str] = set()
    for path in section_paths:
        section_ids = _section_node_ids(snapshot, path)
        if not section_ids:
            unresolved.append(path)
            continue
        for section_id in section_ids:
            chunks.update(collect_chunks_under_section(snapshot, section_id))
    return sorted(chunks), unresolved


def load_bundle_snapshots(bundle_root: Path) -> tuple[str, GraphSnapshot]:
    return load_bundle_snapshot(bundle_root)


def materialize_relevance_labels(
    bundle_root: Path,
    *,
    split: str = "dev",
    min_coverage: float = 0.9,
) -> RelevanceLabelSet:
    snapshot_id, snapshot = load_bundle_snapshots(bundle_root)
    index_path = bundle_root / "corpus" / "graph_node_index.json"
    graph_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    snapshot_accessions = {ref.accession for ref in snapshot.manifest.filing_refs}
    items_path = bundle_root / "items" / f"{split}.jsonl"
    rows: list[dict] = []
    labels_by_item_id: dict[str, list[str]] = {}
    failures: list[RelevanceFailure] = []

    for line in items_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
        if row.get("validation_status") == "rejected":
            continue
        item_id = row["item_id"]
        paths = row.get("expected_section_paths") or []
        if graph_paths:
            paths, _ = resolve_section_paths(
                paths,
                graph_paths,
                snapshot_accessions=snapshot_accessions,
            )
        chunk_ids, unresolved = resolve_item_chunk_ids(snapshot, paths)
        labels_by_item_id[item_id] = chunk_ids
        row["relevant_chunk_ids"] = chunk_ids
        if not chunk_ids:
            reason = "unresolved_path" if unresolved else "no_chunks_under_path"
            failures.append(
                RelevanceFailure(
                    item_id=item_id,
                    expected_section_paths=paths,
                    reason=reason,
                )
            )

    accepted = [r for r in rows if r.get("validation_status") != "rejected"]
    labeled = sum(1 for r in accepted if r.get("relevant_chunk_ids"))
    coverage = labeled / len(accepted) if accepted else 0.0
    labels_hash = compute_labels_hash(labels_by_item_id)

    sidecar = RelevanceLabelSet(
        labels_hash=labels_hash,
        snapshot_id=snapshot_id,
        coverage_rate=coverage,
        items_labeled=labeled,
        items_failed=failures,
        labels_by_item_id=labels_by_item_id,
    )

    items_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    (bundle_root / "relevance_labels.json").write_text(
        sidecar.model_dump_json(indent=2),
        encoding="utf-8",
    )
    report = {
        "coverage_rate": coverage,
        "items_labeled": labeled,
        "items_total": len(accepted),
        "failures": [f.model_dump() for f in failures],
    }
    (bundle_root / "relevance_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    manifest_path = bundle_root / "manifest.json"
    if manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_data["relevance_labels_hash"] = labels_hash
        manifest_data["relevance_coverage_rate"] = coverage
        manifest_data["relevance_snapshot_id"] = snapshot_id
        manifest_data["relevance_labels_path"] = "relevance_labels.json"
        manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    if coverage < min_coverage:
        msg = f"Relevance coverage {coverage:.2%} below gate {min_coverage:.0%}"
        raise ValueError(msg)

    return sidecar
