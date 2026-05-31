"""Unit tests for item validator (011)."""

from evaluation.generation.item_validator import validate_item
from models.benchmark_generation import GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


def test_validator_accepts_resolvable_paths():
    item = GeneratedBenchmarkItem(
        item_id="t1",
        question="What is revenue?",
        question_type_tag="metrics",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="100"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=[]),
        expected_section_paths=["acc-1/Item7"],
    )
    validated = validate_item(
        item,
        graph_paths={"acc-1/Item7"},
        snapshot_accessions={"acc-1"},
    )
    assert validated.validation_status == "accepted"


def test_validator_rejects_unknown_path():
    item = GeneratedBenchmarkItem(
        item_id="t2",
        question="What is revenue?",
        question_type_tag="metrics",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="100"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=[]),
        expected_section_paths=["acc-1/Missing"],
    )
    validated = validate_item(
        item,
        graph_paths={"acc-1/Item7"},
        snapshot_accessions={"acc-1"},
    )
    assert validated.validation_status == "rejected"


def test_finder_accepts_rubric_only_ground_truth():
    """FinDER-style items may have null answer when rubric is present."""
    item = GeneratedBenchmarkItem(
        item_id="t3",
        question="What supply chain risks are disclosed?",
        question_type_tag="retrieval-qa",
        inspiration_profile="finder",
        ground_truth=GroundTruth(answer=None, rubric="Score evidence grounding in Item 1A."),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=[]),
        expected_section_paths=["acc-1/Item1A"],
    )
    validated = validate_item(
        item,
        graph_paths={"acc-1/Item1A"},
        snapshot_accessions={"acc-1"},
    )
    assert validated.validation_status == "accepted"


def test_validator_accepts_resolvable_suffix_path():
    item = GeneratedBenchmarkItem(
        item_id="t5",
        question="What are the risk factors?",
        question_type_tag="retrieval-qa",
        inspiration_profile="finder",
        ground_truth=GroundTruth(rubric="Ground in Item 1A."),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=[]),
        expected_section_paths=["acc-1/Item 1A. Risk Factors"],
    )
    validated = validate_item(
        item,
        graph_paths={"acc-1/Item 1A."},
        snapshot_accessions={"acc-1"},
    )
    assert validated.validation_status == "accepted"
    assert validated.expected_section_paths == ["acc-1/Item 1A."]


def test_financebench_rejects_null_answer():
    item = GeneratedBenchmarkItem(
        item_id="t4",
        question="What is revenue?",
        question_type_tag="metrics",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer=None, rubric="some rubric"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=[]),
        expected_section_paths=["acc-1/Item7"],
    )
    validated = validate_item(
        item,
        graph_paths={"acc-1/Item7"},
        snapshot_accessions={"acc-1"},
    )
    assert validated.validation_status == "rejected"
    assert "financebench_requires_answer" in validated.validation_errors
