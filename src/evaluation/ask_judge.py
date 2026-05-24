"""Post-query audit: validate trajectory and run LLM judge (010)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from evaluation.judges.gemini_panel import GeminiJudgePanel, JudgeParseError
from evaluation.validator.trajectory import validate_trajectory
from models.evaluation import JudgeRunSummary, JudgeStatus, ValidationStatus
from models.query import AnswerPackage
from models.trajectory import AgentTrajectorySnapshot
from tracing.mlflow_langgraph import log_judge_verdict, log_trajectory_validation


def load_trajectory_judge_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/trajectory_judge.yaml")
    return yaml.safe_load(path.read_text()) if path.exists() else {}


@dataclass
class PostQueryAuditResult:
    validation_status: ValidationStatus
    judge_summary: JudgeRunSummary | None
    validation_uri: str = ""
    judge_uri: str = ""


def judge_with_retries(
    panel: GeminiJudgePanel,
    snapshot: AgentTrajectorySnapshot,
    answer: AnswerPackage | None,
    question: str,
    *,
    cfg: dict | None = None,
) -> JudgeRunSummary:
    cfg = cfg or load_trajectory_judge_config()
    max_retries = int(cfg.get("max_retries", 3))
    backoffs = list(cfg.get("backoff_seconds") or [1, 2, 4])
    min_score = float(cfg.get("min_score", 0.6))
    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            summary = panel.judge_trajectory(snapshot, answer, question)
            weakest = min(summary.criteria, key=lambda c: c.score) if summary.criteria else None
            if weakest and weakest.score < min_score:
                summary.weakest_criterion_id = weakest.criterion_id
                summary.weakest_stage = weakest.stage
            return summary
        except (JudgeParseError, Exception) as exc:
            last_error = str(exc)
            if attempt < max_retries:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
    return JudgeRunSummary(
        judge_model=panel.model_name,
        judge_config_id="gemini_2_5_pro",
        judge_status=JudgeStatus.DEGRADED,
        retry_count=max_retries,
        error=last_error[:500],
    )


def run_post_query_audit(
    snapshot: AgentTrajectorySnapshot,
    answer: AnswerPackage | None,
    *,
    question: str,
    mlflow_run_id: str,
    panel: GeminiJudgePanel | None = None,
) -> PostQueryAuditResult:
    validation = validate_trajectory(snapshot)
    validation_uri = ""
    judge_uri = ""
    if mlflow_run_id:
        validation_uri = log_trajectory_validation(mlflow_run_id, validation)

    if validation.status != ValidationStatus.COMPLETE:
        skipped = JudgeRunSummary(
            judge_model="n/a",
            judge_config_id="gemini_2_5_pro",
            judge_status=JudgeStatus.NOT_EVALUABLE,
            overall_summary="Trajectory not complete; judge skipped",
        )
        if mlflow_run_id:
            judge_uri = log_judge_verdict(mlflow_run_id, skipped)
        return PostQueryAuditResult(
            validation_status=validation.status,
            judge_summary=skipped,
            validation_uri=validation_uri,
            judge_uri=judge_uri,
        )

    judge_panel = panel or GeminiJudgePanel()
    summary = judge_with_retries(judge_panel, snapshot, answer, question)
    if mlflow_run_id:
        judge_uri = log_judge_verdict(mlflow_run_id, summary)
    return PostQueryAuditResult(
        validation_status=validation.status,
        judge_summary=summary,
        validation_uri=validation_uri,
        judge_uri=judge_uri,
    )
