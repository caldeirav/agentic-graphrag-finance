from evaluation.judges.gemini_panel import GeminiJudgePanel


def test_parse_summary_json():
    panel = GeminiJudgePanel()
    text = """
    {
      "criteria": [
        {"id": "trajectory_coherence", "score": 0.9, "justification": "ok"},
        {"id": "routing_decisions", "score": 0.8, "stage": "macro", "justification": "ok"},
        {"id": "retrieval_fidelity", "score": 0.85, "justification": "ok"},
        {"id": "synthesis_grounding", "score": 0.7, "justification": "ok"}
      ],
      "overall_summary": "good run"
    }
    """
    summary = panel._parse_summary(text)
    assert summary.judge_status.value == "ok"
    assert len(summary.criteria) == 4
    assert summary.weakest_criterion_id == "synthesis_grounding"
