"""Unit tests for is_numeric_answer_gt classifier (016)."""

from evaluation.generation.gt_classifier import is_numeric_answer_gt


def test_percentage_is_numeric() -> None:
    assert is_numeric_answer_gt("20.69%") is True


def test_currency_is_numeric() -> None:
    assert is_numeric_answer_gt("$1.2B") is True


def test_short_label_is_numeric() -> None:
    assert is_numeric_answer_gt("Upstream") is True


def test_narrative_is_not_numeric() -> None:
    text = (
        "Apple reported services revenue growth driven by App Store and cloud offerings "
        "across multiple geographic segments in the fiscal year."
    )
    assert is_numeric_answer_gt(text) is False
