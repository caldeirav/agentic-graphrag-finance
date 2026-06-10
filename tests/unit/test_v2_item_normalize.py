"""Tests for v2 item post-parse normalization (017)."""

from evaluation.generation.item_validator import validate_item
from evaluation.generation.v2_item_normalize import normalize_v2_item
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


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
