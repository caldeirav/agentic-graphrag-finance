"""Batch benchmark evaluation runner."""

from __future__ import annotations

import json
import os
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

            effective_snapshot_id = snapshot_id
            for ds_name in suite.datasets:
                if ds_name == "custom-judge":
                    os.environ.setdefault("OFFLINE_BENCHMARK", "1")
                    dataset = self._registry.get(ds_name)
                    from evaluation.datasets.custom_judge import CustomJudgeDataset

                    if not isinstance(dataset, CustomJudgeDataset):
                        raise TypeError("custom-judge registry entry must be CustomJudgeDataset")
                    manifest = dataset.manifest()
                    bundle = manifest.corpus_bundle
                    if not (dataset._root / bundle.corpus_root).is_dir():
                        msg = (
                            f"Custom-judge corpus missing under {dataset._root / bundle.corpus_root}. "
                            "Run `git lfs pull` for bundled corpus artifacts."
                        )
                        raise FileNotFoundError(msg)
                    effective_snapshot_id = bundle.snapshot_id
                    sampling_path = dataset._root / manifest.sampling_manifest_path
                    generation_seed = ""
                    if sampling_path.is_file():
                        generation_seed = str(
                            json.loads(sampling_path.read_text()).get("random_seed", "")
                        )
                    mlflow.log_params(
                        {
                            "custom_judge_version": manifest.version,
                            "items_hash": manifest.items_hash,
                            "snapshot_id": bundle.snapshot_id,
                            "generation_seed": generation_seed,
                            "generation_judge_version": manifest.generation_judge_version,
                            "evaluation_judge_version": manifest.evaluation_judge_version,
                        }
                    )

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
                        snap = api.get_snapshot(effective_snapshot_id)
                        acc_set = set(item.temporal_scope.accessions)
                        pre_bound = [
                            r for r in snap.manifest.filing_refs if r.accession in acc_set
                        ]
                    resp = query_service.answer(
                        QueryRequest(
                            query=item.question,
                            snapshot_id=effective_snapshot_id,
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
                            traj_data = client.load_dict(
                                resp.mlflow_run_id, "agent_trajectory.json"
                            )
                            from models.trajectory import AgentTrajectorySnapshot

                            snap = AgentTrajectorySnapshot.model_validate(traj_data)
                            trajectory = build_trajectory_from_state(
                                {
                                    "query": item.question,
                                    "query_id": snap.query_id,
                                    "filing_set": [],
                                    "evidence_chunks": resp.answer.citations
                                    if resp.answer
                                    else [],
                                    "status": snap.status,
                                }
                            )
                        except Exception:
                            trajectory = build_trajectory_from_state(
                                {"evidence_chunks": resp.answer.citations if resp.answer else []}
                            )

                    if resp.judge_status and resp.judge_scores:
                        from models.evaluation import JudgeCriterionResult, JudgeVerdict

                        criteria = [
                            JudgeCriterionResult(
                                criterion_id=k, score=v, justification="from ask audit"
                            )
                            for k, v in resp.judge_scores.items()
                        ]
                        verdict = JudgeVerdict(
                            judge_model=resp.judge_status,
                            judge_version="ask-audit",
                            rationale=resp.validation_status,
                            scores=resp.judge_scores,
                            criteria=criteria,
                        )
                    else:
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
                            validation_status=resp.validation_status,
                            judge_status=resp.judge_status,
                            outcome_score=verdict.scores.get(
                                "synthesis_grounding",
                                verdict.scores.get("value_alignment", 0),
                            ),
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
            snapshot_id=effective_snapshot_id,
            judge_config_id="gemini_2_5_pro",
            items=results,
        )
        out = report_dir or Path("reports")
        out.mkdir(parents=True, exist_ok=True)
        _write_reports(eval_run, out / f"benchmark-{run_id[:8]}")
        from evaluation.gate import compute_gate_report, load_gate_config
        from models.evaluation import ValidationStatus

        val_statuses = []
        degraded = 0
        for r in results:
            if r.validation_status:
                val_statuses.append(ValidationStatus(r.validation_status))
            else:
                val_statuses.append(ValidationStatus.INCOMPLETE)
            if r.judge_status == "degraded":
                degraded += 1
        cfg = load_gate_config()
        gate = compute_gate_report(
            val_statuses,
            threshold=float(cfg.get("gate_threshold", 0.9)),
            judge_degraded=degraded,
        )
        gate_path = out / f"benchmark-{run_id[:8]}" / "trajectory_gate.txt"
        gate_path.write_text(gate.format_summary())
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
