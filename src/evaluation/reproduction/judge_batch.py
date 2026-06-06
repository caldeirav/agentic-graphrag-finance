"""Batched trajectory judging for deferred reproduction runs (013)."""

from __future__ import annotations

import json
import time
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
from evaluation.reproduction.result_write import prepare_result_for_write
from models.evaluation import BenchmarkItem, BenchmarkResult
from tracing.mlflow_langgraph import build_trajectory_from_state
from tracing.trajectory_export import normalize_trajectory_state

_RESERVED_DIRS = frozenset({"tables", "assets", "__pycache__"})


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"


def _discover_variant_dirs(output_dir: Path, variant_id: str | None) -> list[Path]:
    return sorted(
        p
        for p in output_dir.iterdir()
        if p.is_dir()
        and p.name not in _RESERVED_DIRS
        and not p.name.startswith(".")
        and (variant_id is None or p.name == variant_id)
    )


def _parse_judge_version(version: str) -> int:
    raw = (version or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    digits = "".join(ch for ch in raw if ch.isdigit())
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0


def _has_hydrated_evidence(trajectory_snapshot: dict | None) -> bool:
    if not trajectory_snapshot:
        return False
    state = normalize_trajectory_state(trajectory_snapshot)
    chunks = state.get("evidence_chunks") or []
    return len(chunks) > 0


def _should_skip_rescore(row: BenchmarkResult) -> bool:
    """Skip items already at judge v2+ with non-empty trajectory evidence."""
    verdict = row.judge_verdict
    if verdict is None:
        return False
    if _parse_judge_version(verdict.judge_version) < 2:
        return False
    return _has_hydrated_evidence(row.trajectory_snapshot)


def _should_judge(row: BenchmarkResult, *, force_rescore: bool) -> bool:
    if force_rescore:
        return (row.judge_status or "").lower() != "not_evaluable"
    if not is_final_judge_status(row.judge_status):
        return True
    return not _should_skip_rescore(row)


def _load_results(path: Path) -> list[BenchmarkResult]:
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkResult.model_validate(row) for row in rows]


def _pending_results(
    results: list[BenchmarkResult],
    *,
    force_rescore: bool = False,
) -> list[BenchmarkResult]:
    return [r for r in results if _should_judge(r, force_rescore=force_rescore)]


def _persist_variant_results(
    results_path: Path,
    order: list[BenchmarkResult],
    updated: dict[str, BenchmarkResult],
) -> None:
    merged = [prepare_result_for_write(updated[r.item_id]) for r in order]
    write_json_atomic(
        results_path,
        [r.model_dump(mode="json") for r in merged],
    )


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
    force_rescore: bool = False,
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
    batch_started = time.perf_counter()
    stats: dict[str, int | float] = {
        "judged": 0,
        "skipped": 0,
        "failed": 0,
        "variants_processed": 0,
    }

    variant_dirs = _discover_variant_dirs(output_dir, variant_id)
    if not variant_dirs:
        log(f"judge-batch: no variant directories found under {output_dir}")
        stats["elapsed_seconds"] = 0.0
        return stats

    plan: list[tuple[Path, list[BenchmarkResult], list[BenchmarkResult]]] = []
    for variant_dir in variant_dirs:
        results_path = variant_dir / "results.json"
        if not results_path.is_file():
            log(f"judge-batch: skip {variant_dir.name} (no results.json)")
            continue
        results = _load_results(results_path)
        pending = _pending_results(results, force_rescore=force_rescore)
        skipped = len(results) - len(pending)
        stats["skipped"] = int(stats["skipped"]) + skipped
        if pending:
            plan.append((variant_dir, results, pending))
        else:
            log(
                f"judge-batch: {variant_dir.name} — 0 pending "
                f"({len(results)} items already scored or resume-skipped)"
            )

    total_pending = sum(len(pending) for _, _, pending in plan)
    log(
        f"judge-batch: split={split!r} bundle={bundle_root.name} "
        f"concurrency={concurrency} force_rescore={force_rescore}"
    )
    log(
        f"judge-batch: {len(plan)} variant(s) to judge, "
        f"{total_pending} item(s) pending, {stats['skipped']} resume-skipped"
    )
    if total_pending == 0:
        stats["elapsed_seconds"] = round(time.perf_counter() - batch_started, 1)
        log(f"judge-batch: nothing to do (finished in {stats['elapsed_seconds']}s)")
        return stats

    judged_so_far = 0

    for variant_dir, results, pending in plan:
        variant_name = variant_dir.name
        results_path = variant_dir / "results.json"
        variant_started = time.perf_counter()
        already_scored = len(results) - len(pending)
        if already_scored:
            log(
                f"judge-batch: [{variant_name}] resuming — "
                f"{already_scored} already scored, {len(pending)} pending"
            )
        else:
            log(f"judge-batch: [{variant_name}] starting {len(pending)} item(s)...")

        def _work(row: BenchmarkResult) -> BenchmarkResult:
            item = items_by_id.get(row.item_id)
            if item is None:
                return row.model_copy(update={"judge_status": "not_evaluable"})
            return _judge_one(item, row, panel)

        updated: dict[str, BenchmarkResult] = {r.item_id: r for r in results}
        variant_done = 0
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = {pool.submit(_work, row): row.item_id for row in pending}
            for fut in as_completed(futures):
                item_id = futures[fut]
                try:
                    updated[item_id] = prepare_result_for_write(fut.result())
                    stats["judged"] = int(stats["judged"]) + 1
                    variant_done += 1
                    judged_so_far += 1
                    _persist_variant_results(results_path, results, updated)
                    elapsed = time.perf_counter() - batch_started
                    avg = elapsed / judged_so_far
                    remaining = total_pending - judged_so_far
                    eta = _format_duration(avg * remaining) if remaining else "0s"
                    log(
                        f"judge-batch: [{variant_name}] "
                        f"{variant_done}/{len(pending)} "
                        f"({judged_so_far}/{total_pending} total) "
                        f"item={item_id} elapsed={_format_duration(elapsed)} eta~{eta}"
                    )
                except Exception as exc:
                    stats["failed"] = int(stats["failed"]) + 1
                    variant_done += 1
                    judged_so_far += 1
                    _persist_variant_results(results_path, results, updated)
                    log(f"judge-batch: [{variant_name}] FAILED item={item_id}: {exc}")

        _persist_variant_results(results_path, results, updated)
        stats["variants_processed"] = int(stats["variants_processed"]) + 1
        variant_elapsed = time.perf_counter() - variant_started
        log(
            f"judge-batch: [{variant_name}] done in {_format_duration(variant_elapsed)} "
            f"({variant_done} processed, checkpoint saved)"
        )

    stats["elapsed_seconds"] = round(time.perf_counter() - batch_started, 1)
    log(
        f"judge-batch: complete — judged={stats['judged']} skipped={stats['skipped']} "
        f"failed={stats['failed']} elapsed={_format_duration(float(stats['elapsed_seconds']))}"
    )
    return stats
