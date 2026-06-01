"""Graph-structural benchmark metrics (012)."""

from __future__ import annotations

from models.evaluation import BenchmarkItem
from models.reproduction import StructuralMetrics


def accession_binding_hit(item: BenchmarkItem, used_accessions: set[str]) -> bool:
    expected = set(item.expected_bindings.accessions if item.expected_bindings else [])
    if not expected:
        return True
    return expected.issubset(used_accessions)


def section_path_hit(item: BenchmarkItem, visited_paths: set[str]) -> bool:
    expected = set(item.expected_section_paths or [])
    if not expected:
        return True
    return any(path in visited_paths or any(path in v for v in visited_paths) for path in expected)


def multi_filing_success(item: BenchmarkItem, used_accessions: set[str]) -> bool:
    if not item.multi_filing_required:
        return True
    expected = set(item.expected_bindings.accessions if item.expected_bindings else [])
    if len(expected) < 2:
        return True
    return len(expected.intersection(used_accessions)) >= 2


def aggregate_structural_metrics(
    items: list[BenchmarkItem],
    *,
    used_accessions_by_item: dict[str, set[str]],
    visited_paths_by_item: dict[str, set[str]],
) -> StructuralMetrics:
    if not items:
        return StructuralMetrics()
    acc_hits = 0
    section_hits = 0
    multi_hits = 0
    multi_total = 0
    for item in items:
        used = used_accessions_by_item.get(item.item_id, set())
        paths = visited_paths_by_item.get(item.item_id, set())
        if accession_binding_hit(item, used):
            acc_hits += 1
        if section_path_hit(item, paths):
            section_hits += 1
        if item.multi_filing_required:
            multi_total += 1
            if multi_filing_success(item, used):
                multi_hits += 1
    n = len(items)
    return StructuralMetrics(
        accession_binding_accuracy=acc_hits / n,
        section_path_hit_rate=section_hits / n,
        multi_filing_success_rate=(multi_hits / multi_total) if multi_total else 0.0,
    )
