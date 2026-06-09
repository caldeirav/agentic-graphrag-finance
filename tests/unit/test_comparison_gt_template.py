"""Unit tests for comparison_structured ground truth template (017)."""

from evaluation.generation.comparison_gt import (
    derive_comparison_claims,
    validate_comparison_structured,
)
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem


def _comparison_item(**overrides) -> GeneratedBenchmarkItem:
    base = {
        "item_id": "v2-finagentbench-001",
        "question": "Do both filings discuss supply chain risk in MD&A?",
        "question_type_tag": "cross-filing-comparison",
        "answer_type": "comparison_structured",
        "inspiration_profile": "finagentbench",
        "ground_truth": {
            "answer": (
                "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A."
            ),
            "required_claims": [
                "FY2025 10-K discusses supply chain risk in Item 7 MD&A.",
                "FY2024 10-K discusses supply chain risk in Item 7 MD&A.",
                "The comparison spans both bound filings.",
            ],
        },
        "expected_bindings": {
            "accessions": ["0000320193-25-000079", "0000320193-24-000123"],
        },
        "expected_section_paths": [],
        "multi_filing_required": True,
        "operation_class": "QUALITATIVE",
    }
    base.update(overrides)
    return GeneratedBenchmarkItem.model_validate(base)


def test_valid_comparison_item_passes() -> None:
    assert validate_comparison_structured(_comparison_item()) == []


def test_comparison_requires_three_claims() -> None:
    item = _comparison_item(
        ground_truth={
            "answer": "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A.",
            "required_claims": ["only one claim"],
        }
    )
    assert "required_claims" in validate_comparison_structured(item)


def test_derive_comparison_claims_minimum_three() -> None:
    claims = derive_comparison_claims(
        "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A.",
        label_a="FY2025 10-K",
        label_b="FY2024 10-K",
        topic="supply chain risk",
        section="Item 7 MD&A",
    )
    assert len(claims) == 3
    assert "comparison spans" in claims[-1].lower()


def test_invalid_answer_missing_both_filings_pattern() -> None:
    item = _comparison_item(
        ground_truth={
            "answer": "Supply chain risk is discussed.",
            "required_claims": [
                "FY2025 10-K discusses supply chain risk in Item 7 MD&A.",
                "FY2024 10-K discusses supply chain risk in Item 7 MD&A.",
                "The comparison spans both bound filings.",
            ],
        }
    )
    assert "invalid_answer_type" in validate_comparison_structured(item)
