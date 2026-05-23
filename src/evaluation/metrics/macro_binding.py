"""Macro filing-set binding metrics (008)."""

from __future__ import annotations

from models.evaluation import BenchmarkItem


def binding_set_match(predicted: list[str], expected: list[str]) -> bool:
    return set(predicted) == set(expected)


def macro_binding_accuracy(
    predicted_by_item: dict[str, list[str]],
    items: list[BenchmarkItem],
) -> float:
    """Fraction of items with exact accession set match."""
    if not items:
        return 0.0
    hits = 0
    for item in items:
        expected = (item.expected_bindings.accessions if item.expected_bindings else []) or []
        predicted = predicted_by_item.get(item.item_id, [])
        if item.expect_binding_failure:
            if not predicted:
                hits += 1
            continue
        if binding_set_match(predicted, expected):
            hits += 1
    return hits / len(items)


def multi_filing_rate(items: list[BenchmarkItem]) -> float:
    if not items:
        return 0.0
    flagged = sum(1 for i in items if i.multi_filing_required)
    return flagged / len(items)


def macro_fail_closed_rate(
    outcomes: dict[str, bool],
    items: list[BenchmarkItem],
) -> float:
    """Fraction of expect_binding_failure items that actually failed closed."""
    targets = [i for i in items if i.expect_binding_failure]
    if not targets:
        return 1.0
    hits = sum(1 for i in targets if outcomes.get(i.item_id, False))
    return hits / len(targets)
