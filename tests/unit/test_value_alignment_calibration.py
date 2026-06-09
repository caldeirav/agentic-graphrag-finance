"""Mock-judge calibration bands for graded value_alignment (v3.1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from evaluation.judges.gemini_panel import GeminiJudgePanel
from models.evaluation import BenchmarkItem, GroundTruth
from models.query import AnswerPackage

CASES = json.loads(
    (Path(__file__).parent.parent / "fixtures/judge_calibration/cases.json").read_text()
)


def test_mock_value_alignment_calibration_bands() -> None:
    os.environ["USE_MOCK_JUDGE"] = "1"
    panel = GeminiJudgePanel()
    for case in CASES:
        gt = GroundTruth(**case["ground_truth"])
        item = BenchmarkItem(
            item_id=case["id"],
            dataset="custom-judge",
            question="calibration",
            ground_truth=gt,
        )
        answer = AnswerPackage(text=case["answer_text"], citations=[])
        verdict = panel.judge(item, answer, None, variant_id="graph-full")
        va = float(verdict.scores.get("value_alignment", -1))
        assert case["expected_va_min"] <= va <= case["expected_va_max"], (
            f"{case['id']}: va={va} not in [{case['expected_va_min']}, {case['expected_va_max']}]"
        )
        assert verdict.judge_version == "v3.1"
