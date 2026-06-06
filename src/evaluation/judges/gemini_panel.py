"""Gemini 2.5 Pro external judge panel."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

import yaml

from evaluation.judges.outcome_scoring import criteria_for_item
from models.evaluation import (
    BenchmarkItem,
    GroundTruth,
    JudgeCriterionResult,
    JudgeRunSummary,
    JudgeStatus,
    JudgeVerdict,
)
from models.query import AnswerPackage, TrajectoryRecord
from models.trajectory import AgentTrajectorySnapshot

TRAJECTORY_CRITERION_IDS = (
    "trajectory_coherence",
    "routing_decisions",
    "retrieval_fidelity",
    "synthesis_grounding",
)

# Backward-compatible alias for tests and imports.
CRITERION_IDS = TRAJECTORY_CRITERION_IDS


class JudgeParseError(Exception):
    """Raised when judge response is not valid JSON."""


def load_judge_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/judges/gemini_2_5_pro.yaml")
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class GeminiJudgePanel:
    def __init__(self, config_path: Path | None = None) -> None:
        self._cfg = load_judge_config(config_path)
        self._model = self._cfg.get("model", "gemini-2.5-pro")

    @property
    def model_name(self) -> str:
        return self._model

    def judge(
        self,
        item: BenchmarkItem,
        answer: AnswerPackage | None,
        trajectory: TrajectoryRecord | None,
    ) -> JudgeVerdict:
        if os.environ.get("USE_MOCK_JUDGE", "0") == "1":
            return self._mock_verdict_legacy(item, answer, trajectory)

        snapshot = None
        if trajectory is not None:
            from tracing.trajectory_export import build_agent_trajectory_snapshot

            state = {
                "query": item.question,
                "filing_set": trajectory.document_route,
                "graph_traversal": [v.model_dump() for v in trajectory.graph_traversal],
                "evidence_chunks": trajectory.evidence,
                "macro_plan": trajectory.plan,
                "macro_binding": trajectory.macro_binding,
                "status": trajectory.status,
            }
            snapshot = build_agent_trajectory_snapshot(state)
        if snapshot is None:
            from models.trajectory import TrajectoryPlan

            snapshot = AgentTrajectorySnapshot(
                query_id=item.item_id,
                query_text=item.question,
                plan=TrajectoryPlan(
                    intent_summary=item.question,
                    chosen_path_rationale="no trajectory",
                ),
            )
        criteria_ids = criteria_for_item(item)
        summary = self.judge_trajectory(
            snapshot,
            answer,
            item.question,
            ground_truth=item.ground_truth,
            criteria_ids=criteria_ids,
        )
        scores = {c.criterion_id: c.score for c in summary.criteria}
        return JudgeVerdict(
            judge_model=summary.judge_model,
            judge_version="v2",
            rationale=summary.overall_summary[:500],
            scores=scores,
            criteria=summary.criteria,
        )

    def judge_trajectory(
        self,
        snapshot: AgentTrajectorySnapshot,
        answer: AnswerPackage | None,
        question: str,
        *,
        ground_truth: GroundTruth | None = None,
        criteria_ids: tuple[str, ...] | None = None,
    ) -> JudgeRunSummary:
        if os.environ.get("USE_MOCK_JUDGE", "0") == "1":
            return self._mock_summary(snapshot, answer, question, criteria_ids=criteria_ids)

        expected = criteria_ids or TRAJECTORY_CRITERION_IDS
        prompt = self._build_trajectory_prompt(
            snapshot,
            answer,
            question,
            ground_truth=ground_truth,
            criteria_ids=expected,
        )
        from langchain_core.messages import HumanMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=self._model,
            temperature=float(self._cfg.get("temperature", 0)),
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        return self._parse_summary(text, criteria_ids=expected)

    def _parse_summary(
        self,
        text: str,
        *,
        criteria_ids: tuple[str, ...] | None = None,
    ) -> JudgeRunSummary:
        expected = criteria_ids or TRAJECTORY_CRITERION_IDS
        try:
            data = _extract_json(text)
        except json.JSONDecodeError as exc:
            raise JudgeParseError(str(exc)) from exc
        criteria_raw = data.get("criteria") or []
        criteria: list[JudgeCriterionResult] = []
        for entry in criteria_raw:
            cid = str(entry.get("id") or entry.get("criterion_id") or "")
            if cid not in expected:
                continue
            criteria.append(
                JudgeCriterionResult(
                    criterion_id=cid,
                    score=float(entry.get("score", 0)),
                    justification=str(entry.get("justification", ""))[:2000],
                    stage=entry.get("stage"),
                )
            )
        if len(criteria) < len(expected):
            raise JudgeParseError(f"expected {len(expected)} criteria, got {len(criteria)}")
        weakest = min(criteria, key=lambda c: c.score)
        return JudgeRunSummary(
            judge_model=self._model,
            judge_config_id="gemini_2_5_pro",
            judge_status=JudgeStatus.OK,
            criteria=criteria,
            overall_summary=str(data.get("overall_summary", ""))[:1000],
            weakest_criterion_id=weakest.criterion_id,
            weakest_stage=weakest.stage,
        )

    def _mock_summary(
        self,
        snapshot: AgentTrajectorySnapshot,
        answer: AnswerPackage | None,
        question: str,
        *,
        criteria_ids: tuple[str, ...] | None = None,
    ) -> JudgeRunSummary:
        has_answer = answer is not None and bool(answer.text)
        has_ev = len(snapshot.evidence) > 0
        base = 0.88 if has_answer and has_ev else 0.35
        expected = criteria_ids or TRAJECTORY_CRITERION_IDS
        criteria = [
            JudgeCriterionResult(
                criterion_id=cid,
                score=base,
                justification=f"mock judge for {snapshot.query_id[:8]}",
                stage=None,
            )
            for cid in expected
        ]
        return JudgeRunSummary(
            judge_model="mock-judge",
            judge_config_id="gemini_2_5_pro",
            judge_status=JudgeStatus.OK,
            criteria=criteria,
            overall_summary=f"mock evaluation: {question[:80]}",
        )

    def _mock_verdict_legacy(
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
                "trajectory_coherence": traj,
                "routing_decisions": base,
                "retrieval_fidelity": traj,
                "synthesis_grounding": base,
                "value_alignment": base,
                "claim_presence": base,
                "trajectory_fidelity": traj,
            },
        )

    def _build_trajectory_prompt(
        self,
        snapshot: AgentTrajectorySnapshot,
        answer: AnswerPackage | None,
        question: str,
        *,
        ground_truth: GroundTruth | None = None,
        criteria_ids: tuple[str, ...] | None = None,
    ) -> str:
        rubrics = self._cfg.get("rubrics", {})
        as_of = snapshot.evaluation_as_of or date.today().isoformat()
        traj_json = snapshot.model_dump_json()[:12000]
        expected = criteria_ids or TRAJECTORY_CRITERION_IDS
        gt_block = ""
        if ground_truth is not None:
            gt_parts: list[str] = []
            if ground_truth.answer:
                gt_parts.append(f"- expected_answer: {ground_truth.answer[:2000]}")
            if ground_truth.rubric:
                gt_parts.append(f"- expected_rubric: {ground_truth.rubric[:2000]}")
            if gt_parts:
                gt_block = (
                    "\nGround truth for this item (use only when scoring value_alignment "
                    "or claim_presence):\n"
                    + "\n".join(gt_parts)
                    + "\n"
                    "- Score value_alignment 0.0 when the answer abstains (e.g. "
                    "'Insufficient evidence') but ground truth expects a substantive answer.\n"
                    "- Score claim_presence 0.0 when required rubric claims are missing or the "
                    "answer abstains without justification.\n"
                )
        example_criteria = ", ".join(
            f'{{"id": "{cid}", "score": 0.9, "stage": null, "justification": "..."}}'
            for cid in expected[:4]
        )
        return (
            "You are an expert auditor for SEC disclosure Q&A agents.\n\n"
            "Evaluation context (authoritative — do not override):\n"
            f"- evaluation_as_of: {as_of}\n"
            "- document_route entries are real SEC EDGAR filings from the user's "
            "materialized corpus snapshot (not hypothetical).\n"
            "- Use filed_at and period_end on each route entry when judging dates.\n"
            "- trajectory_coherence measures internal consistency (plan → route → hops → "
            "evidence), NOT whether fiscal year labels match your training cutoff.\n"
            f"{gt_block}\n"
            f"Question: {question}\n"
            f"Answer: {answer.text if answer else 'N/A'}\n"
            f"Trajectory JSON:\n{traj_json}\n\n"
            f"Rubrics:\n{yaml.dump(rubrics)}\n\n"
            "Return ONLY valid JSON with this shape (use your own scores 0.0-1.0, not placeholders):\n"
            f'{{"criteria": [{example_criteria}, ...], "overall_summary": "..."}}\n'
            f"Score all criteria: {', '.join(expected)} on 0.0-1.0.\n"
        )
