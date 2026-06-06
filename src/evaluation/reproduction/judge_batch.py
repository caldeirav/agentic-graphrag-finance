"""Batched trajectory judging for deferred reproduction runs (013)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections.abc import Callable

from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.generation.api_retry import with_transient_retry
from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.judges.outcome_scoring import compute_outcome_scores
from evaluation.metrics.trajectory import trajectory_fidelity_score
from evaluation.reproduction.defer_config import is_final_judge_status
from evaluation.reproduction.io import write_json_atomic
from models.evaluation import BenchmarkItem, BenchmarkResult
from tracing.mlflow_langgraph import build_trajectory_from_state


def _load_results(path: Path) -> list[BenchmarkResult]:
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkResult.model_validate(row) for row in rows]


def _pending_results(results: list[BenchmarkResult]) -> list[BenchmarkResult]:
    return [r for r in results if not is_final_judge_status(r.judge_status)]


def _judge_one(
    item: BenchmarkItem,
    result: BenchmarkResult,
    judge: GeminiJudgePanel,
) -> BenchmarkResult:
    if result.trajectory_snapshot:
        trajectory = build_trajectory_from_state(result.trajectory_snapshot)
    else:
        citations = result.answer.citations if result.answer else []
        trajectory = build_trajectory_from_state(
            {"evidence_chunks": citations, "query": item.question}
        )
    if not trajectory.evidence and result.answer and result.answer.citations:
        trajectory = trajectory.model_copy(update={"evidence": list(result.answer.citations)})
    verdict = with_transient_retry(
        lambda: judge.judge(item, result.answer, trajectory),
        label="GeminiJudge",
    )
    traj_score = trajectory_fidelity_score(
        trajectory, judge_score=verdict.scores.get("trajectory_fidelity")
    )
    outcome_score, alignment_score = compute_outcome_scores(item, result.answer, verdict)
    return result.model_copy(
        update={
            "judge_status": "ok",
            "judge_verdict": verdict,
            "outcome_score": outcome_score,
            "alignment_score": alignment_score,
            "trajectory_fidelity": traj_score,
            "mlflow_run_id": result.generation_mlflow_run_id or result.mlflow_run_id,
        }
    )


def run_judge_batch(
    output_dir: Path,
    *,
    bundle_root: Path,
    split: str,
    custom_judge_version: str = "",
    judge: GeminiJudgePanel | None = None,
    variant_id: str | None = None,
    concurrency: int = 2,
    max_items: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Score pending items in per-variant results.json files."""
    panel = judge or GeminiJudgePanel()
    version = custom_judge_version
    if not version:
        manifest_path = bundle_root / "manifest.json"
        if manifest_path.is_file():
            version = json.loads(manifest_path.read_text(encoding="utf-8")).get("version", "")
    ds = CustomJudgeDataset(version=version, bundle_root=bundle_root)
    items_by_id = {item.item_id: item for item in ds.load_split(split)}
    if max_items:
        keep = set(list(items_by_id.keys())[:max_items])
        items_by_id = {k: v for k, v in items_by_id.items() if k in keep}

    log = progress or (lambda _msg: None)
    stats = {"judged": 0, "skipped": 0, "failed": 0}

    variant_dirs = [
        p
        for p in output_dir.iterdir()
        if p.is_dir() and (variant_id is None or p.name == variant_id)
    ]
    for variant_dir in sorted(variant_dirs):
        results_path = variant_dir / "results.json"
        if not results_path.is_file():
            continue
        results = _load_results(results_path)
        pending = _pending_results(results)
        stats["skipped"] += len(results) - len(pending)
        if not pending:
            continue

        log(f"judge-batch {variant_dir.name}: {len(pending)} pending")

        def _work(row: BenchmarkResult) -> BenchmarkResult:
            item = items_by_id.get(row.item_id)
            if item is None:
                return row.model_copy(update={"judge_status": "not_evaluable"})
            return _judge_one(item, row, panel)

        updated: dict[str, BenchmarkResult] = {r.item_id: r for r in results}
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = {pool.submit(_work, row): row.item_id for row in pending}
            for fut in as_completed(futures):
                item_id = futures[fut]
                try:
                    updated[item_id] = fut.result()
                    stats["judged"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    log(f"  judge failed {item_id}: {exc}")

        merged = [updated[r.item_id] for r in results]
        write_json_atomic(
            results_path,
            [r.model_dump(mode="json") for r in merged],
        )
    return stats
