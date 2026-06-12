"""Tests for custom-judge v2 bundle repair helpers."""

from __future__ import annotations

from evaluation.generation.bundle_repair_v2 import repair_expected_section_paths_row
from evaluation.generation.numeric_gt import normalize_numeric_gt, numeric_values_equivalent
from evaluation.generation.path_sanitize import is_corrupt_section_path


def test_corrupt_sentence_fragment_detected() -> None:
    path = "0000034088-26-000067/$ 1.1 billion from its divestment activities"
    assert is_corrupt_section_path(path)


def test_item_1a_path_not_corrupt() -> None:
    path = "0000034088-26-000067/Item 1A. Risk Factors"
    assert not is_corrupt_section_path(path)


def test_normalize_numeric_gt_formats() -> None:
    assert normalize_numeric_gt("$1.1 billion") == "1100000000"
    assert normalize_numeric_gt("1.1") == "1.1"
    assert numeric_values_equivalent("1100000000", "$1.1 billion")


def test_repair_expected_section_paths_row() -> None:
    graph_paths = {
        "0000034088-26-000067/Item 1A. Risk Factors",
        "0000018230-26-000021/Item 1A. Risk Factors",
        "0000034088-26-000067/$ 1.1 billion from divestment",
    }
    row = {
        "question": "Compare risk factors across the two filings.",
        "ground_truth": {"answer": "Both discuss risks in Item 1A."},
        "expected_bindings": {
            "accessions": [
                "0000034088-26-000067",
                "0000018230-26-000021",
            ],
        },
        "expected_section_paths": [
            "0000034088-26-000067/sanctions, trade tariffs, or policies affecting our business",
            "0000018230-26-000021/organizations, or other actors against our core business",
        ],
    }
    paths, changed = repair_expected_section_paths_row(
        row,
        graph_paths,
        snapshot_accessions=set(row["expected_bindings"]["accessions"]),
    )
    assert changed
    assert all("Item 1A" in p or "RISK" in p.upper() for p in paths)
