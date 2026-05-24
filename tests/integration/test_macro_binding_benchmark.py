"""Macro binding benchmark gate (US5 / SC-001 SC-002)."""

from evaluation.datasets.finagentbench import FinAgentBenchDataset
from evaluation.metrics.macro_binding import macro_binding_accuracy, multi_filing_rate
from retrieval.macro.binding_eval import run_macro_binding_eval


def test_macro_binding_dataset_slice_contract():
    items = FinAgentBenchDataset().load_macro_binding_slice()
    assert len(items) >= 50
    assert multi_filing_rate(items) >= 0.80
    for item in items[:5]:
        assert item.expected_bindings is not None
        assert item.expected_bindings.accessions


def test_macro_binding_accuracy_gate():
    report = run_macro_binding_eval()
    assert report["total"] >= 50
    assert report["macro_binding_accuracy"] >= 0.70
    assert report["multi_filing_rate"] >= 0.80


def test_macro_binding_accuracy_metric():
    from models.evaluation import BenchmarkItem, ExpectedBindings

    items = [
        BenchmarkItem(
            item_id="a",
            dataset="finagentbench",
            question="q",
            expected_bindings=ExpectedBindings(accessions=["x", "y"]),
        )
    ]
    acc = macro_binding_accuracy({"a": ["y", "x"]}, items)
    assert acc == 1.0
