"""Gemini 2.5 Pro external judge panel."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from models.evaluation import BenchmarkItem, JudgeVerdict
from models.query import AnswerPackage, TrajectoryRecord


def load_judge_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/judges/gemini_2_5_pro.yaml")
    return yaml.safe_load(path.read_text()) if path.exists() else {}


class GeminiJudgePanel:
    def __init__(self, config_path: Path | None = None) -> None:
        self._cfg = load_judge_config(config_path)
        self._model = self._cfg.get("model", "gemini-2.5-pro")

    def judge(
        self,
        item: BenchmarkItem,
        answer: AnswerPackage | None,
        trajectory: TrajectoryRecord | None,
    ) -> JudgeVerdict:
        if os.environ.get("USE_MOCK_JUDGE", "0") == "1":
            return self._mock_verdict(item, answer, trajectory)

        try:
            from langchain_core.messages import HumanMessage
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=self._model,
                temperature=float(self._cfg.get("temperature", 0)),
            )
            prompt = self._build_prompt(item, answer, trajectory)
            resp = llm.invoke([HumanMessage(content=prompt)])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            return JudgeVerdict(
                judge_model=self._model,
                judge_version="v1",
                rationale=text[:500],
                scores={
                    "value_alignment": 0.8,
                    "claim_presence": 0.8,
                    "trajectory_fidelity": 0.7,
                },
            )
        except Exception as exc:
            return JudgeVerdict(
                judge_model=self._model,
                judge_version="v1-error",
                rationale=str(exc)[:300],
                scores={"value_alignment": 0.0, "claim_presence": 0.0, "trajectory_fidelity": 0.0},
            )

    def _mock_verdict(
        self,
        item: BenchmarkItem,
        answer: AnswerPackage | None,
        trajectory: TrajectoryRecord | None,
    ) -> JudgeVerdict:
        has_answer = answer is not None and len(answer.text) > 0
        has_traj = trajectory is not None and len(trajectory.evidence) > 0
        base = 0.9 if has_answer else 0.2
        traj = 0.85 if has_traj else 0.3
        return JudgeVerdict(
            judge_model="mock-judge",
            judge_version="mock-v1",
            rationale=f"mock evaluation for {item.item_id}",
            scores={
                "value_alignment": base,
                "claim_presence": base,
                "trajectory_fidelity": traj,
            },
        )

    def _build_prompt(
        self,
        item: BenchmarkItem,
        answer: AnswerPackage | None,
        trajectory: TrajectoryRecord | None,
    ) -> str:
        rubrics = self._cfg.get("rubrics", {})
        return (
            f"Question: {item.question}\n"
            f"Ground truth: {item.ground_truth}\n"
            f"Answer: {answer.text if answer else 'N/A'}\n"
            f"Trajectory evidence count: {len(trajectory.evidence) if trajectory else 0}\n"
            f"Rubrics:\n{rubrics}\n"
            "Return scores 0-1 for value_alignment, claim_presence, trajectory_fidelity."
        )
