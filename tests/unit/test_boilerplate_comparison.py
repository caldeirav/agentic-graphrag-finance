"""Unit tests for comparison boilerplate gate (018)."""

from evaluation.generation.comparison_gt import (
    is_boilerplate_comparison_answer,
    is_comparison_canonical_answer,
    validate_comparison_structured,
)
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


def _item(answer: str) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem(
        item_id="v2-finagentbench-0099",
        question="Compare geopolitical risk?",
        question_type_tag="cross-filing-comparison",
        answer_type=AnswerType.COMPARISON_STRUCTURED,
        inspiration_profile="finagentbench",
        ground_truth=GroundTruth(
            answer=answer,
            required_claims=[
                "Caterpillar discusses geopolitical risk in Item 1A.",
                "Exxon Mobil discusses geopolitical risk in Item 1A.",
                "Both filings contrast supply-chain cyclicality versus commodity volatility.",
            ],
        ),
        expected_bindings=ExpectedBindings(accessions=["acc-a", "acc-b"]),
        expected_section_paths=["acc-a/Item 1A", "acc-b/Item 1A"],
        multi_filing_required=True,
    )


def test_reject_boilerplate_co_occurrence_only():
    answer = (
        "Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K discuss "
        "geopolitical risks in Item 1A. Risk Factors."
    )
    assert is_boilerplate_comparison_answer(answer) is True
    assert "boilerplate_comparison_answer" in validate_comparison_structured(_item(answer))


def test_accept_substantive_comparison():
    answer = (
        "Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K emphasize geopolitical risk "
        "differently: Caterpillar frames supply-chain cyclicality whereas Exxon Mobil highlights "
        "sanctions and commodity price volatility."
    )
    assert is_comparison_canonical_answer(answer) is True
    assert is_boilerplate_comparison_answer(answer) is False
    assert "boilerplate_comparison_answer" not in validate_comparison_structured(_item(answer))
    assert "invalid_answer_type" not in validate_comparison_structured(_item(answer))
