"""Unit tests for judge rubric prompt assembly (016)."""

from evaluation.judges.gemini_panel import GeminiJudgePanel
from models.evaluation import GroundTruth
from models.trajectory import AgentTrajectorySnapshot, TrajectoryPlan


def test_prompt_includes_required_claims() -> None:
    panel = GeminiJudgePanel()
    gt = GroundTruth(
        answer="Narrative answer about revenue drivers.",
        required_claims=["Services grew year over year", "Mentioned App Store"],
    )
    snapshot = AgentTrajectorySnapshot(
        query_id="q1",
        query_text="What drove growth?",
        plan=TrajectoryPlan(intent_summary="growth", chosen_path_rationale="mda"),
    )
    prompt = panel._build_trajectory_prompt(
        snapshot,
        None,
        "What drove growth?",
        ground_truth=gt,
        criteria_ids=("value_alignment",),
        variant_id="flat-chunk",
    )
    assert "required_claims" in prompt
    assert "Services grew year over year" in prompt
    assert "Variant: flat-chunk" in prompt


def test_config_includes_answer_quality_rubric() -> None:
    panel = GeminiJudgePanel()
    assert "answer_quality" in panel._cfg.get("rubrics", {})
