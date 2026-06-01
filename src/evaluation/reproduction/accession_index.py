"""Accession → issuer snapshot index for per-item subgraph loading (013)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evaluation.reproduction.errors import MissingAccessionsError, TooManyIssuersError
from graph.store import load_snapshot


@dataclass(frozen=True)
class IssuerSnapshotRef:
    ticker: str
    snapshot_id: str

    @property
    def graph_path(self) -> str:
        return f"{self.ticker}/{self.snapshot_id}.graphml"


class AccessionIndex:
    def __init__(
        self,
        accession_to_issuer: dict[str, IssuerSnapshotRef],
        bundle_root: Path,
        *,
        max_issuers_per_item: int = 4,
    ) -> None:
        self.accession_to_issuer = accession_to_issuer
        self.bundle_root = bundle_root
        self.graphs_dir = bundle_root / "corpus" / "graphs"
        self.max_issuers_per_item = max_issuers_per_item

    @classmethod
    def build(cls, bundle_root: Path, *, max_issuers_per_item: int = 4) -> AccessionIndex:
        manifest_path = bundle_root / "manifest.json"
        bundle_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        corpus = bundle_manifest["corpus_bundle"]
        base_dir = bundle_root / corpus.get("corpus_root", "corpus") / "graphs"
        issuer_refs = corpus.get("issuer_snapshots") or []
        accession_to_issuer: dict[str, IssuerSnapshotRef] = {}

        for ref in issuer_refs:
            ticker = ref["ticker"]
            snapshot_id = ref["snapshot_id"]
            graph_path = base_dir / ticker / f"{snapshot_id}.graphml"
            if not graph_path.is_file():
                msg = f"Bundled graph snapshot missing: {graph_path}"
                raise FileNotFoundError(msg)
            snapshot = load_snapshot(ticker, snapshot_id, base_dir)
            for filing in snapshot.manifest.filing_refs:
                acc = filing.accession
                if acc in accession_to_issuer:
                    existing = accession_to_issuer[acc]
                    if existing.ticker != ticker or existing.snapshot_id != snapshot_id:
                        msg = f"Ambiguous accession mapping for {acc}"
                        raise ValueError(msg)
                    continue
                accession_to_issuer[acc] = IssuerSnapshotRef(
                    ticker=ticker,
                    snapshot_id=snapshot_id,
                )

        return cls(accession_to_issuer, bundle_root, max_issuers_per_item=max_issuers_per_item)

    def resolve_accessions(self, item_id: str, accessions: list[str]) -> list[IssuerSnapshotRef]:
        if len(accessions) > self.max_issuers_per_item:
            raise TooManyIssuersError(item_id, len(accessions))
        missing = [a for a in accessions if a not in self.accession_to_issuer]
        if missing:
            raise MissingAccessionsError(item_id, missing)
        seen: set[tuple[str, str]] = set()
        refs: list[IssuerSnapshotRef] = []
        for acc in accessions:
            ref = self.accession_to_issuer[acc]
            key = (ref.ticker, ref.snapshot_id)
            if key not in seen:
                seen.add(key)
                refs.append(ref)
        return refs
