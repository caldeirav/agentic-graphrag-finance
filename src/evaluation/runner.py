"""Batch benchmark evaluation runner."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import mlflow

from contracts.query import QueryRequest
from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.metrics.ranking import compute_ranking_metrics
from evaluation.metrics.trajectory import trajectory_fidelity_score
from evaluation.registry import BenchmarkRegistry, default_registry
from models.evaluation import BenchmarkResult, EvaluationRun
from retrieval.service import QueryService
from tracing.mlflow_langgraph import build_trajectory_from_state, setup_mlflow


@dataclass
class BenchmarkSuite:
    datasets: list[str]
    split: str = "dev"
    max_items: int | None = 100


class EvaluationRunner:
    def __init__(
        self,
        registry: BenchmarkRegistry | None = None,
        judge: GeminiJudgePanel | None = None,
    ) -> None:
        self._registry = registry or default_registry()
        self._judge = judge or GeminiJudgePanel()

    def run_suite(
        self,
        suite: BenchmarkSuite,
        snapshot_id: str,
        query_service: QueryService,
        *,
        issuer_id: str = "",
        report_dir: Path | None = None,
    ) -> EvaluationRun:
        setup_mlflow()
        run_id = str(uuid.uuid4())
        results: list[BenchmarkResult] = []

        with mlflow.start_run(run_name=f"benchmark-{suite.split}-{run_id[:8]}"):
            parent_run = mlflow.active_run()
            parent_id = parent_run.info.run_id if parent_run else ""

            for ds_name in suite.datasets:
                dataset = self._registry.get(ds_name)
                items = dataset.load_split(suite.split)
                if suite.max_items:
                    items = items[: suite.max_items]

                for item in items:
                    if item.temporal_scope is None and ds_name in (
                        "finagentbench",
                        "corpus_binding",
                    ):
                        raise ValueError(
                            f"Benchmark item {item.item_id} missing required temporal_scope"
                        )
                    pre_bound = []
                    if item.temporal_scope and item.temporal_scope.accessions:
                        from graph.query_api import LocalGraphQueryAPI

                        api = LocalGraphQueryAPI(
                            query_service._graph_base, issuer_id or "AAPL"
                        )
                        snap = api.get_snapshot(snapshot_id)
                        acc_set = set(item.temporal_scope.accessions)
                        pre_bound = [
                            r for r in snap.manifest.filing_refs if r.accession in acc_set
                        ]
                    resp = query_service.answer(
                        QueryRequest(
                            query=item.question,
                            snapshot_id=snapshot_id,
                            pre_bound_filings=pre_bound,
                            metadata={"issuer_id": issuer_id, "benchmark_item": item.item_id},
                        )
                    )
                    citations = resp.answer.citations if resp.answer else []
                    retrieved = [c.chunk_node_id for c in citations]
                    ranking = compute_ranking_metrics(retrieved, item.relevant_chunk_ids)
                    trajectory = None
                    if resp.mlflow_run_id:
                        try:
                            from mlflow.tracking import MlflowClient

                            client = MlflowClient()
                            traj_data = client.load_dict(resp.mlflow_run_id, "trajectory.json")
                            from models.query import TrajectoryRecord

                            trajectory = TrajectoryRecord.model_validate(traj_data)
                        except Exception:
                            trajectory = build_trajectory_from_state(
                                {"evidence_chunks": resp.answer.citations if resp.answer else []}
                            )

                    verdict = self._judge.judge(item, resp.answer, trajectory)
                    traj_score = trajectory_fidelity_score(
                        trajectory or build_trajectory_from_state({}),
                        judge_score=verdict.scores.get("trajectory_fidelity"),
                    )
                    results.append(
                        BenchmarkResult(
                            item_id=item.item_id,
                            answer=resp.answer,
                            mlflow_run_id=resp.mlflow_run_id,
                            outcome_score=verdict.scores.get("value_alignment", 0),
                            alignment_score=verdict.scores.get("claim_presence", 0),
                            trajectory_fidelity=traj_score,
                            ranking_metrics=ranking,
                            judge_verdict=verdict,
                        )
                    )

            mlflow.log_metric("mean_outcome_score", _mean(results, "outcome_score"))
            mlflow.log_metric("mean_trajectory_fidelity", _mean(results, "trajectory_fidelity"))

        eval_run = EvaluationRun(
            run_id=run_id,
            suite_name=suite.split,
            snapshot_id=snapshot_id,
            judge_config_id="gemini_2_5_pro",
            items=results,
        )
        out = report_dir or Path("reports")
        out.mkdir(parents=True, exist_ok=True)
        _write_reports(eval_run, out / f"benchmark-{run_id[:8]}")
        if parent_id:
            mlflow.log_artifacts(str(out / f"benchmark-{run_id[:8]}"))
        return eval_run


def _mean(results: list[BenchmarkResult], field: str) -> float:
    vals = [getattr(r, field) for r in results]
    return sum(vals) / len(vals) if vals else 0.0


def _write_reports(eval_run: EvaluationRun, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_id": eval_run.run_id,
        "snapshot_id": eval_run.snapshot_id,
        "item_count": len(eval_run.items),
        "mean_outcome": _mean(eval_run.items, "outcome_score"),
        "mean_alignment": _mean(eval_run.items, "alignment_score"),
        "mean_trajectory_fidelity": _mean(eval_run.items, "trajectory_fidelity"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    by_dataset: dict[str, list] = defaultdict(list)
    for item in eval_run.items:
        ds = item.item_id.split("-")[0]
        by_dataset[ds].append(item.model_dump(mode="json"))
    (out_dir / "by_dataset.json").write_text(json.dumps(dict(by_dataset), indent=2, default=str))
