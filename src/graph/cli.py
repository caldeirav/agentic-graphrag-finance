"""CLI: build knowledge graph from parsed filings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from graph.builder import build_snapshot
from graph.store import save_snapshot
from models.parsing import ParsedDocument


def main() -> None:
    parser = argparse.ArgumentParser(description="Build knowledge graph")
    parser.add_argument("--issuer", required=True, help="CIK or issuer id")
    parser.add_argument("--parsed-dir", type=Path, default=Path("data/parsed"))
    parser.add_argument("--out", type=Path, default=Path("data/graphs"))
    parser.add_argument("--snapshot-id", default="")
    args = parser.parse_args()

    issuer_dir = args.parsed_dir / args.issuer
    docs: list[ParsedDocument] = []
    for path in sorted(issuer_dir.glob("*.json")):
        docs.append(ParsedDocument.model_validate_json(path.read_text()))

    if not docs:
        raise SystemExit(f"No parsed documents in {issuer_dir}")

    snapshot = build_snapshot(args.issuer, docs, snapshot_id=args.snapshot_id or None)
    graph_path = save_snapshot(snapshot, args.out)
    print(
        json.dumps(
            {
                "snapshot_id": snapshot.snapshot_id,
                "graph": str(graph_path),
                "nodes": len(snapshot.nodes),
                "edges": len(snapshot.edges),
            }
        )
    )


if __name__ == "__main__":
    main()
