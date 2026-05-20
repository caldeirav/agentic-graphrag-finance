"""Issuer-level graph snapshot registry and stale probing."""

from __future__ import annotations

import fcntl
import uuid
from contextlib import contextmanager
from pathlib import Path

from graph.builder import build_snapshot
from graph.reachability import audit_snapshot_reachability, save_reachability_report
from graph.store import load_snapshot, save_snapshot
from ingestion.corpus import corpus_definition_hash
from ingestion.edgar_client import list_recent_filings
from models.corpus import CorpusDefinition, IssuerSnapshotIndex, SnapshotIndexEntry
from models.filing import FilingRef
from models.graph import GraphSnapshot
from models.parsing import ParsedDocument


def _index_path(issuer_id: str, base_dir: Path) -> Path:
    return base_dir / issuer_id / "index.json"


def _lock_path(issuer_id: str, base_dir: Path) -> Path:
    return base_dir / issuer_id / ".materialize.lock"


@contextmanager
def issuer_materialize_lock(issuer_id: str, base_dir: Path):
    """Exclusive lock for snapshot version increments per issuer."""
    lock_file = _lock_path(issuer_id, base_dir)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def load_index(issuer_id: str, base_dir: Path) -> IssuerSnapshotIndex:
    path = _index_path(issuer_id, base_dir)
    if not path.exists():
        return IssuerSnapshotIndex(issuer_id=issuer_id)
    return IssuerSnapshotIndex.model_validate_json(path.read_text())


def save_index(index: IssuerSnapshotIndex, base_dir: Path) -> None:
    path = _index_path(index.issuer_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2))


def register_snapshot(
    snapshot: GraphSnapshot,
    base_dir: Path,
    *,
    corpus_definition_hash: str = "",
    audit_ready: bool = False,
    audit_pass_rate: float | None = None,
    reachability_artifact: str = "",
) -> None:
    with issuer_materialize_lock(snapshot.issuer_id, base_dir):
        index = load_index(snapshot.issuer_id, base_dir)
        entry = SnapshotIndexEntry(
            snapshot_id=snapshot.snapshot_id,
            created_at=snapshot.manifest.created_at,
            filing_refs=list(snapshot.manifest.filing_refs),
            corpus_definition_hash=corpus_definition_hash,
            graph_builder_version=snapshot.manifest.graph_builder_version,
            audit_ready=audit_ready,
            audit_pass_rate=audit_pass_rate,
            reachability_artifact=reachability_artifact,
        )
        index.versions.append(entry)
        index.latest_snapshot_id = snapshot.snapshot_id
        save_index(index, base_dir)


def get_latest_snapshot_id(issuer_id: str, base_dir: Path) -> str | None:
    index = load_index(issuer_id, base_dir)
    return index.latest_snapshot_id or None


def get_latest_snapshot(issuer_id: str, base_dir: Path) -> GraphSnapshot | None:
    sid = get_latest_snapshot_id(issuer_id, base_dir)
    if not sid:
        return None
    return load_snapshot(issuer_id, sid, base_dir)


def build_issuer_snapshot(
    issuer_id: str,
    documents: list[ParsedDocument],
    *,
    snapshot_id: str | None = None,
    base_dir: Path | None = None,
    corpus_definition: CorpusDefinition | None = None,
    run_audit: bool = True,
) -> GraphSnapshot:
    out_dir = base_dir or Path("data/graphs")
    sid = snapshot_id or str(uuid.uuid4())
    snapshot = build_snapshot(issuer_id, documents, snapshot_id=sid)

    audit_ready = False
    audit_pass_rate: float | None = None
    reachability_path = ""
    if run_audit and snapshot.nodes:
        report = audit_snapshot_reachability(snapshot)
        reachability_path = str(
            save_reachability_report(report, out_dir).relative_to(out_dir)
        )
        audit_ready = report.audit_ready
        audit_pass_rate = report.pass_rate
        snapshot.manifest.audit_ready = audit_ready
        snapshot.manifest.audit_pass_rate = audit_pass_rate
        snapshot.manifest.reachability_artifact = reachability_path

    save_snapshot(snapshot, out_dir)
    c_hash = corpus_definition_hash(corpus_definition) if corpus_definition else ""
    register_snapshot(
        snapshot,
        out_dir,
        corpus_definition_hash=c_hash,
        audit_ready=audit_ready,
        audit_pass_rate=audit_pass_rate,
        reachability_artifact=reachability_path,
    )
    return snapshot


def probe_stale_filings(
    snapshot: GraphSnapshot,
    *,
    ticker: str | None = None,
) -> list[FilingRef]:
    """Return filings on EDGAR newer than the newest filing in the snapshot."""
    if not snapshot.manifest.filing_refs:
        return []
    issuer = ticker or snapshot.issuer_id
    cik = snapshot.manifest.filing_refs[0].cik
    max_filed = max(r.filed_at for r in snapshot.manifest.filing_refs)
    snapshot_accessions = {r.accession for r in snapshot.manifest.filing_refs}
    try:
        recent = list_recent_filings(cik=cik, ticker=issuer, max_per_form=4)
    except Exception:
        return []
    newer: list[FilingRef] = []
    for res in recent:
        if res.accession in snapshot_accessions:
            continue
        if res.filed_at > max_filed:
            newer.append(
                FilingRef(
                    cik=res.cik,
                    accession=res.accession,
                    form_type=res.form_type,
                    filed_at=res.filed_at,
                    period_end=res.period_end,
                    source_uri=res.edgar_filing_url,
                )
            )
    return newer
