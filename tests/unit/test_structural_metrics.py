"""Unit tests for structural metrics (012)."""

from evaluation.reproduction.structural import (
    accession_binding_hit,
    aggregate_structural_metrics,
    multi_filing_success,
    section_path_hit,
)
from models.enums import OperationClass
from models.evaluation import BenchmarkItem, ExpectedBindings


def _item(**kwargs) -> BenchmarkItem:
    defaults = {
        "item_id": "i1",
        "dataset": "custom-judge",
        "question": "q",
        "operation_class": OperationClass.QUALITATIVE,
    }
    defaults.update(kwargs)
    return BenchmarkItem(**defaults)


def test_accession_binding_hit_when_subset_used() -> None:
    item = _item(expected_bindings=ExpectedBindings(accessions=["0000320193-24-000123"]))
    assert accession_binding_hit(item, {"0000320193-24-000123", "extra"}) is True


def test_accession_binding_miss() -> None:
    item = _item(expected_bindings=ExpectedBindings(accessions=["0000320193-24-000123"]))
    assert accession_binding_hit(item, {"0000320193-24-000076"}) is False


def test_accession_binding_vacuous_when_no_expected() -> None:
    item = _item()
    assert accession_binding_hit(item, set()) is True


def test_section_path_hit_prefix() -> None:
    item = _item(expected_section_paths=["0000320193-24-000123/Item7"])
    assert section_path_hit(item, {"0000320193-24-000123/Item7/MD&A"}) is True


def test_section_path_miss() -> None:
    item = _item(expected_section_paths=["0000320193-24-000123/Item7"])
    assert section_path_hit(item, {"0000320193-24-000076/Item1"}) is False


def test_multi_filing_success_requires_two_accessions() -> None:
    item = _item(
        multi_filing_required=True,
        expected_bindings=ExpectedBindings(
            accessions=["0000320193-24-000123", "0000320193-24-000076"]
        ),
    )
    assert multi_filing_success(item, {"0000320193-24-000123"}) is False
    assert multi_filing_success(
        item, {"0000320193-24-000123", "0000320193-24-000076"}
    ) is True


def test_aggregate_structural_metrics() -> None:
    items = [
        _item(
            item_id="a",
            expected_bindings=ExpectedBindings(accessions=["acc1"]),
            expected_section_paths=["acc1/Item7"],
        ),
        _item(
            item_id="b",
            expected_bindings=ExpectedBindings(accessions=["acc2", "acc3"]),
            multi_filing_required=True,
        ),
    ]
    metrics = aggregate_structural_metrics(
        items,
        used_accessions_by_item={"a": {"acc1"}, "b": {"acc2"}},
        visited_paths_by_item={"a": {"acc1/Item7"}, "b": set()},
    )
    assert metrics.accession_binding_accuracy == 0.5
    assert metrics.multi_filing_success_rate == 0.0
