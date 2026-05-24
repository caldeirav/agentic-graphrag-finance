"""Judge prompt includes corpus evaluation context (010)."""

from datetime import date

from evaluation.judges.gemini_panel import GeminiJudgePanel
from models.trajectory import AgentTrajectorySnapshot, FilingRouteEntry, TrajectoryPlan


def test_trajectory_prompt_includes_evaluation_context():
    panel = GeminiJudgePanel()
    snap = AgentTrajectorySnapshot(
        query_id="q1",
        query_text="YoY sales",
        evaluation_as_of="2026-05-20",
        plan=TrajectoryPlan(intent_summary="compare", chosen_path_rationale="yoy"),
        document_route=[
            FilingRouteEntry(
                accession="0000320193-25-000079",
                form_type="10-K",
                cik="0000320193",
                filed_at="2025-11-01",
                period_end="2025-09-27",
                fiscal_period_label="FY2025",
            ),
        ],
    )
    prompt = panel._build_trajectory_prompt(snap, None, "YoY sales?")
    assert "evaluation_as_of" in prompt
    assert "2026-05-20" in prompt
    assert "real SEC EDGAR" in prompt
    assert '"score": 0.0' not in prompt
    assert "trajectory_coherence" in prompt
