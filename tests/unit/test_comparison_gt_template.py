"""Unit tests for comparison_structured ground truth template (017)."""

from evaluation.generation.comparison_gt import (
    COMPARISON_ANSWER_PROMPT_RULES,
    comparison_claims_are_structured,
    derive_comparison_claims,
    extract_comparison_entities,
    format_generation_validation_feedback,
    is_cross_filing_claim,
    validate_comparison_structured,
)
from models.benchmark_generation import GeneratedBenchmarkItem


def _comparison_item(**overrides) -> GeneratedBenchmarkItem:
    base = {
        "item_id": "v2-finagentbench-001",
        "question": "Do both filings discuss supply chain risk in MD&A?",
        "question_type_tag": "cross-filing-comparison",
        "answer_type": "comparison_structured",
        "inspiration_profile": "finagentbench",
        "ground_truth": {
            "answer": (
                "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A, "
                "with FY2025 emphasizing inventory buffers whereas FY2024 emphasizes supplier "
                "diversification."
            ),
            "required_claims": [
                "FY2025 10-K discusses supply chain risk in Item 7 MD&A.",
                "FY2024 10-K discusses supply chain risk in Item 7 MD&A.",
                "Both filings emphasize supply chain risk as a material factor in Item 7 MD&A.",
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
            "answer": (
                "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A, "
                "with FY2025 emphasizing inventory buffers whereas FY2024 emphasizes supplier "
                "diversification."
            ),
            "required_claims": ["only one claim"],
        }
    )
    assert "required_claims" in validate_comparison_structured(item)


def test_derive_comparison_claims_minimum_three() -> None:
    answer = "Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A."
    claims = derive_comparison_claims(
        answer,
        label_a="FY2025 10-K",
        label_b="FY2024 10-K",
        topic="supply chain risk",
        section="Item 7 MD&A",
    )
    assert len(claims) == 3
    assert comparison_claims_are_structured(claims, answer=answer)


def test_emphasize_pattern_passes_invalid_answer_type_gate() -> None:
    answer = (
        "Both Caterpillar and Exxon Mobil emphasize different risks, with Caterpillar "
        "highlighting cyclical demand whereas Exxon Mobil stresses commodity volatility."
    )
    item = _comparison_item(
        ground_truth={
            "answer": answer,
            "required_claims": [
                "Caterpillar highlights cyclical demand in its 2025 10-K risk factors.",
                "Exxon Mobil stresses commodity volatility in its 2025 10-K risk factors.",
                "Both issuers contrast cyclical demand versus commodity volatility in risk disclosures.",
            ],
        }
    )
    assert "invalid_answer_type" not in validate_comparison_structured(item)
    entity_a, entity_b = extract_comparison_entities(answer)
    assert entity_a == "Caterpillar"
    assert entity_b == "Exxon Mobil"


def test_invalid_answer_missing_both_filings_pattern() -> None:
    item = _comparison_item(
        ground_truth={
            "answer": "Supply chain risk is discussed.",
            "required_claims": [
                "FY2025 10-K discusses supply chain risk in Item 7 MD&A.",
                "FY2024 10-K discusses supply chain risk in Item 7 MD&A.",
                "Both filings emphasize supply chain risk as a material factor in Item 7 MD&A.",
            ],
        }
    )
    assert "invalid_answer_type" in validate_comparison_structured(item)


def test_natural_cross_filing_synthesis_claim() -> None:
    answer = (
        "Both Exxon Mobil's 2025 10-K and Caterpillar's 2025 10-K discuss risks "
        "associated with their international operations in the 'Risk Factors' section."
    )
    claims = [
        "In its 2025 10-K, Exxon Mobil states its business is subject to geopolitical risk abroad.",
        "In its 2025 10-K, Caterpillar identifies risks related to international trade policies.",
        "Both companies explicitly state in their Risk Factors sections that international "
        "operations expose them to significant geopolitical and trade-related risks.",
    ]
    entity_a, entity_b = extract_comparison_entities(answer)
    assert entity_a is not None and entity_b is not None
    assert is_cross_filing_claim(claims[-1], entity_a=entity_a, entity_b=entity_b)
    assert comparison_claims_are_structured(claims, answer=answer)


def test_boilerplate_cross_claim_not_required() -> None:
    answer = (
        "Both FY2025 10-K and FY2024 10-K discuss revenue growth in Item 7 MD&A."
    )
    claims = [
        "FY2025 10-K reports revenue growth in Item 7 MD&A.",
        "FY2024 10-K reports revenue growth in Item 7 MD&A.",
        "Revenue growth is a shared theme across both filings in Item 7 MD&A.",
    ]
    assert comparison_claims_are_structured(claims, answer=answer)


def test_format_feedback_includes_comparison_rules_for_finagentbench() -> None:
    text = format_generation_validation_feedback(
        ["invalid_answer_type"],
        profile="finagentbench",
    )
    assert "invalid_answer_type" in text
    assert COMPARISON_ANSWER_PROMPT_RULES.strip() in text
    assert "Both {filing A} and {filing B}" in text


def test_format_feedback_parses_semicolon_delimited_codes() -> None:
    text = format_generation_validation_feedback(
        "boilerplate_comparison_answer; required_claims",
        profile="finagentbench",
    )
    assert "boilerplate_comparison_answer" in text
    assert "required_claims" in text
    assert "whereas" in text


def test_format_feedback_empty_returns_empty() -> None:
    assert format_generation_validation_feedback(None) == ""
    assert format_generation_validation_feedback([]) == ""
