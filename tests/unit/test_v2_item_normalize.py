"""Tests for v2 item post-parse normalization (017)."""

from evaluation.generation.item_validator import validate_item
from evaluation.generation.v2_item_normalize import normalize_v2_item
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem


def _item(**kwargs) -> GeneratedBenchmarkItem:
    base = {
        "item_id": "v2-fin-001",
        "question": "What was total revenue in FY2025?",
        "question_type_tag": "metrics-generated",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "$394.3 billion"},
        "expected_bindings": {"accessions": ["0000320193-24-000123"]},
        "expected_section_paths": ["0000320193-24-000123/item_7"],
        "operation_class": "QUALITATIVE",
    }
    base.update(kwargs)
    return GeneratedBenchmarkItem.model_validate(base)


def test_numeric_financebench_gets_no_required_claims() -> None:
    item = normalize_v2_item(_item(answer_type="narrative"))
    assert item.answer_type == AnswerType.NUMERIC
    assert item.ground_truth.required_claims is None


def test_narrative_derives_minimum_two_claims() -> None:
    item = normalize_v2_item(
        _item(
            answer_type="narrative",
            ground_truth={
                "answer": "The company expanded international operations significantly during the period.",
            },
        )
    )
    claims = item.ground_truth.required_claims or []
    assert len(claims) >= 2


def test_comparison_keeps_natural_claims_without_boilerplate() -> None:
    answer = (
        "Both Exxon Mobil's 2025 10-K and Caterpillar's 2025 10-K discuss risks "
        "in the Risk Factors section."
    )
    raw = GeneratedBenchmarkItem.model_validate(
        {
            "item_id": "v2-finagentbench-010",
            "question": "How do Exxon and Caterpillar describe international risk?",
            "question_type_tag": "cross-filing-comparison",
            "answer_type": "comparison_structured",
            "inspiration_profile": "finagentbench",
            "ground_truth": {
                "answer": answer,
                "required_claims": [
                    "In its 2025 10-K, Exxon Mobil cites geopolitical instability abroad.",
                    "In its 2025 10-K, Caterpillar cites international trade policy risk.",
                    "Both companies highlight international operations as a major risk theme.",
                ],
            },
            "expected_bindings": {
                "accessions": ["0000320193-25-000079", "0000320193-24-000123"],
            },
            "expected_section_paths": ["0000320193-25-000079/item_1a"],
            "operation_class": "QUALITATIVE",
        }
    )
    item = normalize_v2_item(raw)
    claims = item.ground_truth.required_claims or []
    assert "comparison spans both bound filings" not in " ".join(claims).lower()
    assert len(claims) >= 3


def test_emphasize_answer_derives_entity_labels() -> None:
    answer = (
        "Both Caterpillar and Exxon Mobil emphasize different risks, with Caterpillar "
        "highlighting cyclical demand whereas Exxon Mobil stresses commodity volatility."
    )
    raw = GeneratedBenchmarkItem.model_validate(
        {
            "item_id": "v2-finagentbench-011",
            "question": "How do Caterpillar and Exxon Mobil frame risk?",
            "question_type_tag": "cross-filing-comparison",
            "answer_type": "comparison_structured",
            "inspiration_profile": "finagentbench",
            "ground_truth": {"answer": answer, "required_claims": []},
            "expected_bindings": {
                "accessions": ["0000320193-25-000079", "0000320193-24-000123"],
            },
            "expected_section_paths": ["0000320193-25-000079/item_1a"],
            "operation_class": "QUALITATIVE",
        }
    )
    item = normalize_v2_item(raw)
    claims = item.ground_truth.required_claims or []
    assert len(claims) >= 3
    joined = " ".join(claims).lower()
    assert "caterpillar" in joined
    assert "exxon" in joined


def test_normalize_passes_validator_for_numeric() -> None:
    item = normalize_v2_item(_item(answer_type=None))
    validated = validate_item(
        item,
        graph_paths={"0000320193-24-000123/item_7"},
        snapshot_accessions={"0000320193-24-000123"},
        bundle_version="2.0.0",
    )
    assert validated.validation_status == "accepted"
    assert "required_claims" not in validated.validation_errors
