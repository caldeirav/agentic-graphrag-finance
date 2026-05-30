"""Shared snapshot loading helpers for reproduction (012)."""

from __future__ import annotations

import json
from pathlib import Path

from graph.store import load_snapshot
from models.graph import GraphSnapshot


def load_bundle_snapshot(bundle_root: Path) -> tuple[str, GraphSnapshot]:
    bundle_manifest = json.loads((bundle_root / "manifest.json").read_text(encoding="utf-8"))
    corpus = bundle_manifest["corpus_bundle"]
    ref = corpus["issuer_snapshots"][0]
    base_dir = bundle_root / corpus.get("corpus_root", "corpus") / "graphs"
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
    snapshot = load_snapshot(ticker, snapshot_id, base_dir)
    return corpus["snapshot_id"], snapshot
