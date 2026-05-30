"""Unit tests for deduplicator (012)."""

from evaluation.generation.deduplicator import deduplicate_items
from models.benchmark_generation import GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


def _item(item_id: str, question: str) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem(
        item_id=item_id,
        question=question,
        question_type_tag="mock",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="x"),
        expected_bindings=ExpectedBindings(accessions=["a"], fiscal_periods=[]),
        expected_section_paths=["a/Item7"],
        validation_status="accepted",
    )


def test_deduplicator_rejects_similar_questions():
    items = [
        _item("1", "What is total revenue for fiscal 2024?"),
        _item("2", "What is total revenue for fiscal 2024"),
    ]
    accepted, rejected = deduplicate_items(items, threshold=0.85)
    assert len(accepted) == 1
    assert len(rejected) == 1
