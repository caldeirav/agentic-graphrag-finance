"""Tests for v2 macro-bindability feasibility (017)."""

from evaluation.generation.feasibility_macro import check_item_macro_bindable
from models.benchmark_generation import GeneratedBenchmarkItem


def _item(accessions: list[str]) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": "v2-fin-001",
            "question": "What was revenue?",
            "question_type_tag": "metrics-generated",
            "inspiration_profile": "financebench",
            "ground_truth": {"answer": "42"},
            "expected_bindings": {"accessions": accessions},
            "expected_section_paths": ["0000320193-24-000123/item_7"],
            "operation_class": "QUALITATIVE",
        }
    )


def test_check_item_macro_bindable_uses_snapshot_filing_refs(aapl_macro_snapshot) -> None:
    acc = aapl_macro_snapshot.manifest.filing_refs[0].accession
    ok, detail = check_item_macro_bindable(_item([acc]), aapl_macro_snapshot)
    assert ok, detail


def test_missing_accession_in_manifest_fails(aapl_macro_snapshot) -> None:
    ok, detail = check_item_macro_bindable(_item(["0000999999-99-999999"]), aapl_macro_snapshot)
    assert not ok
    assert "not in corpus manifest" in detail
