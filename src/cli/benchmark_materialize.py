"""Materialize sampled corpus into draft bundle (011 CLI facade)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from cli.corpus_pipeline import run_materialize_pipeline
from models.benchmark_generation import (
    CorpusBundle,
    GenerationReport,
    IssuerSnapshotRef,
    SamplingManifest,
)
from models.corpus import CorpusDefinition, CorpusDefinitionMode, CorpusMemberStatus
from models.enums import GraphNodeType
from models.graph import GraphSnapshot


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _export_graph_node_index(snapshot: GraphSnapshot) -> list[str]:
    paths: list[str] = []
    accessions = [r.accession for r in snapshot.manifest.filing_refs]
    default_acc = accessions[0] if accessions else ""
    for node in snapshot.nodes:
        if node.node_type not in (GraphNodeType.SECTION, GraphNodeType.DOCUMENT):
            continue
        slug = node.properties.get("section_slug") or node.label or node.node_id
        accession = default_acc
        for candidate in accessions:
            if candidate in node.source_ref or candidate.replace("-", "") in node.node_id:
                accession = candidate
                break
        if accession:
            paths.append(f"{accession}/{slug}")
    return sorted(set(paths))


def _copy_snapshot_into_bundle(
    *,
    graphs_root: Path,
    ticker: str,
    snapshot_id: str,
    draft_dir: Path,
    artifact_hashes: dict[str, str],
) -> int:
    """Copy snapshot GraphML + manifest into draft corpus/graphs/{ticker}/."""
    src_dir = graphs_root / ticker
    dest_dir = draft_dir / "corpus" / "graphs" / ticker
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    graphml = dest_dir / f"{snapshot_id}.graphml"
    for suffix in (".graphml", ".manifest.json", ".reachability.json"):
        src = src_dir / f"{snapshot_id}{suffix}"
        if not src.is_file():
            continue
        dest = dest_dir / f"{snapshot_id}{suffix}"
        shutil.copy2(src, dest)
        rel = dest.relative_to(draft_dir).as_posix()
        artifact_hashes[rel] = _sha256_file(dest)
        copied += dest.stat().st_size
    if not graphml.is_file():
        return -1
    return copied


def materialize_sampled_corpus(
    sampling: SamplingManifest,
    draft_dir: Path,
    *,
    graphs_root: Path | None = None,
    run_id: str,
) -> tuple[CorpusBundle, GenerationReport]:
    """Materialize each sampled issuer and assemble corpus bundle under draft_dir."""
    graphs_root = graphs_root or Path("data/graphs")
    corpus_root = draft_dir / "corpus"
    corpus_root.mkdir(parents=True, exist_ok=True)

    issuer_refs: list[IssuerSnapshotRef] = []
    all_paths: set[str] = set()
    artifact_hashes: dict[str, str] = {}
    total_bytes = 0
    failures: dict[str, int] = {}

    for issuer in sampling.selected_issuers:
        accessions = issuer.accessions
        if not accessions:
            failures[f"no_filings_sampled:{issuer.ticker}"] = failures.get(
                f"no_filings_sampled:{issuer.ticker}", 0
            ) + 1
            continue
        defn = CorpusDefinition(
            issuer_id=issuer.ticker,
            mode=CorpusDefinitionMode.EXPLICIT_ACCESSIONS,
            form_types=["10-K", "10-Q"],
            max_filings=max(1, len(accessions)),
            accessions=accessions,
        )
        job = run_materialize_pipeline(defn, ticker=issuer.ticker, graphs_dir=graphs_root)
        if not job.snapshot_id:
            failures["materialize_no_snapshot"] = failures.get("materialize_no_snapshot", 0) + 1
            continue
        from graph.store import load_snapshot

        snapshot = load_snapshot(issuer.ticker, job.snapshot_id, graphs_root)
        if snapshot is None:
            failures["snapshot_load_failed"] = failures.get("snapshot_load_failed", 0) + 1
            continue

        copied_bytes = _copy_snapshot_into_bundle(
            graphs_root=graphs_root,
            ticker=issuer.ticker,
            snapshot_id=job.snapshot_id,
            draft_dir=draft_dir,
            artifact_hashes=artifact_hashes,
        )
        if copied_bytes < 0:
            failures["snapshot_copy_failed"] = failures.get("snapshot_copy_failed", 0) + 1
            continue
        total_bytes += copied_bytes

        for path in _export_graph_node_index(snapshot):
            all_paths.add(path)

        rel = Path("graphs") / issuer.ticker / job.snapshot_id
        issuer_refs.append(
            IssuerSnapshotRef(
                ticker=issuer.ticker,
                snapshot_id=job.snapshot_id,
                relative_path=str(rel).replace("\\", "/"),
            )
        )
        for member in job.members:
            if member.status == CorpusMemberStatus.FAILED:
                key = f"ingestion_failed:{member.resolution.accession}"
                failures[key] = failures.get(key, 0) + 1

    index_path = corpus_root / "graph_node_index.json"
    index_path.write_text(json.dumps({"paths": sorted(all_paths)}, indent=2) + "\n")
    artifact_hashes[str(index_path.relative_to(draft_dir)).replace("\\", "/")] = _sha256_file(
        index_path
    )
    total_bytes += index_path.stat().st_size

    snapshot_ids = sorted(ref.snapshot_id for ref in issuer_refs)
    composite_id = (
        snapshot_ids[0]
        if len(snapshot_ids) == 1
        else f"composite-{hashlib.sha256('|'.join(snapshot_ids).encode()).hexdigest()[:16]}"
    )

    bundle = CorpusBundle(
        snapshot_id=composite_id,
        issuer_snapshots=issuer_refs,
        corpus_root="corpus",
        graph_node_index_path="corpus/graph_node_index.json",
        total_bytes=total_bytes,
        artifact_hashes=artifact_hashes,
    )

    report = GenerationReport(
        run_id=run_id,
        candidates_total=0,
        accepted_count=0,
        rejected_count=0,
        pass_rate=0.0,
        rejections_by_reason=failures,
        judge_api_calls=0,
        storage_bytes_used=total_bytes,
        duration_seconds=0.0,
        budget_exceeded=False,
    )
    (draft_dir / "generation_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n"
    )
    (draft_dir / "corpus_bundle.json").write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2) + "\n"
    )
    return bundle, report
