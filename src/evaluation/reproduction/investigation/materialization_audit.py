"""Materialization audit: expected vs visited corpus bindings (019)."""

from __future__ import annotations

import json
from pathlib import Path

from models.benchmark_generation import GeneratedBenchmarkItem
from models.evaluation import BenchmarkResult
from models.investigation import MaterializationAudit


def _bundle_snapshot_id(bundle_root: Path) -> str:
    manifest_path = bundle_root / "manifest.json"
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return str(payload.get("snapshot_id") or payload.get("bundle_version") or "")
    graphs_dir = bundle_root / "corpus" / "graphs"
    if graphs_dir.is_dir():
        manifests = sorted(graphs_dir.glob("**/*.manifest.json"))
        if manifests:
            return manifests[0].stem.replace(".manifest", "")
    return ""


def _visited_from_result(result: BenchmarkResult | None) -> tuple[list[str], list[str], list[str]]:
    if result is None:
        return [], [], []
    visited_accessions: set[str] = set()
    visited_sections: set[str] = set()
    cited_chunks: list[str] = []

    if result.answer and result.answer.citations:
        for citation in result.answer.citations:
            if citation.accession:
                visited_accessions.add(citation.accession)
            if citation.accession and citation.section_id:
                visited_sections.add(f"{citation.accession}/{citation.section_id}")
            if citation.chunk_node_id:
                cited_chunks.append(citation.chunk_node_id)

    snap = result.trajectory_snapshot or {}
    if isinstance(snap, dict):
        for accession in snap.get("visited_accessions") or []:
            visited_accessions.add(str(accession))
        for path in snap.get("visited_section_paths") or []:
            visited_sections.add(str(path))
        doc_route = snap.get("document_route") or []
        for ref in doc_route:
            if isinstance(ref, dict) and ref.get("accession"):
                visited_accessions.add(str(ref["accession"]))

    return sorted(visited_accessions), sorted(visited_sections), cited_chunks


def build_materialization_audit(
    *,
    bundle_root: Path,
    item: GeneratedBenchmarkItem,
    result: BenchmarkResult | None,
) -> MaterializationAudit:
    expected_accessions = list(item.expected_bindings.accessions) if item.expected_bindings else []
    expected_sections = list(item.expected_section_paths or [])
    visited_accessions, visited_sections, cited_chunks = _visited_from_result(result)

    expected_section_set = set(expected_sections)
    visited_section_set = set(visited_sections)
    binding_miss = bool(expected_section_set and not expected_section_set.issubset(visited_section_set))

    if not binding_miss and expected_accessions:
        expected_acc_set = set(expected_accessions)
        visited_acc_set = set(visited_accessions)
        binding_miss = bool(expected_acc_set and not expected_acc_set.issubset(visited_acc_set))

    return MaterializationAudit(
        snapshot_id=_bundle_snapshot_id(bundle_root),
        expected_accessions=expected_accessions,
        visited_accessions=visited_accessions,
        expected_section_paths=expected_sections,
        visited_section_paths=visited_sections,
        cited_chunk_node_ids=cited_chunks,
        binding_miss=binding_miss,
    )
