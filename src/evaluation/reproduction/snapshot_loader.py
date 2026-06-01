"""Shared snapshot loading helpers for reproduction (012)."""

from __future__ import annotations

import json
from pathlib import Path

from graph.store import load_snapshot
from models.graph import GraphManifest, GraphSnapshot


def _merge_snapshots(snapshots: list[GraphSnapshot], composite_id: str) -> GraphSnapshot:
    if not snapshots:
        msg = "Cannot merge empty snapshot list"
        raise ValueError(msg)
    if len(snapshots) == 1:
        return snapshots[0]

    all_nodes = []
    all_edges = []
    all_refs = []
    for snapshot in snapshots:
        all_nodes.extend(snapshot.nodes)
        all_edges.extend(snapshot.edges)
        all_refs.extend(snapshot.manifest.filing_refs)

    first = snapshots[0].manifest
    merged_manifest = GraphManifest(
        created_at=first.created_at,
        filing_refs=all_refs,
        parser_version=first.parser_version,
        graph_builder_version=first.graph_builder_version,
        storage_path="composite",
        node_count=len(all_nodes),
        edge_count=len(all_edges),
        audit_ready=first.audit_ready,
        audit_pass_rate=first.audit_pass_rate,
        reachability_artifact=first.reachability_artifact,
    )
    return GraphSnapshot(
        snapshot_id=composite_id,
        issuer_id="composite",
        nodes=all_nodes,
        edges=all_edges,
        manifest=merged_manifest,
    )


def load_bundle_snapshot(bundle_root: Path) -> tuple[str, GraphSnapshot]:
    """Load all issuer snapshots in a bundle and merge into one composite graph."""
    bundle_manifest = json.loads((bundle_root / "manifest.json").read_text(encoding="utf-8"))
    corpus = bundle_manifest["corpus_bundle"]
    composite_id = corpus["snapshot_id"]
    base_dir = bundle_root / corpus.get("corpus_root", "corpus") / "graphs"
    issuer_refs = corpus.get("issuer_snapshots") or []

    if not issuer_refs:
        msg = "corpus_bundle.issuer_snapshots is empty"
        raise ValueError(msg)

    snapshots: list[GraphSnapshot] = []
    for ref in issuer_refs:
        ticker = ref["ticker"]
        snapshot_id = ref["snapshot_id"]
        graph_path = base_dir / ticker / f"{snapshot_id}.graphml"
        if not graph_path.is_file():
            msg = (
                f"Bundled graph snapshot missing: {graph_path}. "
                "Re-run `agent-query benchmark-dataset generate` for this draft, or copy "
                f"data/graphs/{ticker}/{snapshot_id}.graphml into the bundle corpus."
            )
            raise FileNotFoundError(msg)
        snapshots.append(load_snapshot(ticker, snapshot_id, base_dir))

    return composite_id, _merge_snapshots(snapshots, composite_id)
