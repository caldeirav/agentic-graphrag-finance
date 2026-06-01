"""Multi-variant reproduction runner (012)."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import mlflow

from contracts.query import QueryRequest
from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.metrics.ranking import compute_ranking_metrics
from evaluation.metrics.trajectory import trajectory_fidelity_score
from evaluation.reproduction.corpus_verify import dry_run_registry_check, verify_corpus_hashes
from evaluation.reproduction.export import (
    build_variant_summary,
    export_paper_tables,
    write_paper_tables,
)
from evaluation.reproduction.flat_chunk import FlatChunkBaseline
from evaluation.reproduction.manifest import (
    load_expected_checksums,
    load_release_manifest,
    resolve_variant_configs,
    sha256_file,
)
from evaluation.reproduction.relevance import materialize_relevance_labels
from evaluation.reproduction.snapshot_loader import load_bundle_snapshot
from evaluation.reproduction.verify_tables import verify_tables
from graph.query_api import InMemoryGraphQueryAPI
from models.evaluation import BenchmarkItem, BenchmarkResult
from models.graph import GraphSnapshot
from models.reproduction import (
    EvalRunRef,
    ReleaseManifest,
    ReproRun,
    SystemVariantConfig,
    VariantBackend,
)
from retrieval.service import QueryService
from tracing.mlflow_langgraph import build_trajectory_from_state, setup_mlflow

_LIVE_EVAL_RELEASE_TAGS = frozenset({"paper-v1.0", "paper-live-smoke"})


def _require_live_eval(release_tag: str) -> None:
    """Paper/live-smoke repro must use live Gemini judge and agent LLM."""
    if release_tag not in _LIVE_EVAL_RELEASE_TAGS:
        return
    if os.environ.get("USE_MOCK_JUDGE", "0").strip().lower() in {"1", "true", "yes"}:
        msg = (
            f"Release {release_tag} requires live Gemini judge "
            "(unset USE_MOCK_JUDGE or set USE_MOCK_JUDGE=0)"
        )
        raise RuntimeError(msg)
    if os.environ.get("USE_MOCK_LLM", "0").strip().lower() in {"1", "true", "yes"}:
        msg = (
            f"Release {release_tag} requires live agent LLM "
            "(unset USE_MOCK_LLM or set USE_MOCK_LLM=0; LM Studio must be running)"
        )
        raise RuntimeError(msg)
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        msg = f"Release {release_tag} requires GOOGLE_API_KEY for live judge scoring"
        raise RuntimeError(msg)


@dataclass
class ItemContext:
    inspiration_profile: str
    ground_truth: dict
    relevant_chunk_ids: list[str]


def _progress(message: str) -> None:
    print(message, flush=True)


def _write_variant_results(path: Path, results: list[BenchmarkResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.model_dump(mode="json") for r in results], indent=2, default=str),
        encoding="utf-8",
    )


class ReproRunner:
    def __init__(
        self,
        manifest_path: Path,
        *,
        repo_root: Path | None = None,
        judge: GeminiJudgePanel | None = None,
    ) -> None:
        self._repo_root = repo_root or Path.cwd()
        self._manifest_path = manifest_path
        self._manifest = load_release_manifest(manifest_path)
        self._judge = judge or GeminiJudgePanel()
        self._composite_snapshot: GraphSnapshot | None = None
        self._composite_snapshot_id: str | None = None

    @property
    def manifest(self) -> ReleaseManifest:
        return self._manifest

    def verify_corpus(self) -> None:
        if os.environ.get("OFFLINE_BENCHMARK", "").strip() not in {"1", "true", "yes"}:
            msg = "OFFLINE_BENCHMARK=1 is required for reproduction"
            raise RuntimeError(msg)
        result = verify_corpus_hashes(self._manifest, repo_root=self._repo_root)
        if not result.ok:
            raise RuntimeError(result.message)
        dry_run_registry_check(self._manifest, repo_root=self._repo_root)

    def materialize_relevance(self) -> None:
        bundle = self._repo_root / self._manifest.custom_judge_bundle_path
        materialize_relevance_labels(bundle, split=self._manifest.eval_split)

    def _relevance_ready(self, bundle_root: Path) -> bool:
        sidecar = bundle_root / "relevance_labels.json"
        if not sidecar.is_file():
            return False
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return float(data.get("coverage_rate") or 0.0) >= 0.9

    def _load_composite_snapshot(self, bundle_root: Path) -> tuple[str, GraphSnapshot]:
        if self._composite_snapshot is None or self._composite_snapshot_id is None:
            snapshot_id, snapshot = load_bundle_snapshot(bundle_root)
            self._composite_snapshot_id = snapshot_id
            self._composite_snapshot = snapshot
            _progress(
                f"Loaded composite corpus graph ({len(snapshot.nodes)} nodes, "
                f"{len(snapshot.manifest.filing_refs)} filings)"
            )
        return self._composite_snapshot_id, self._composite_snapshot

    def run_variant(
        self,
        variant: SystemVariantConfig,
        *,
        max_items: int | None = None,
        output_dir: Path,
    ) -> tuple[list[BenchmarkResult], EvalRunRef]:
        bundle_root = self._repo_root / self._manifest.custom_judge_bundle_path
        ds = CustomJudgeDataset(
            version=self._manifest.custom_judge_version,
            bundle_root=bundle_root,
        )
        items = ds.load_split(self._manifest.eval_split)
        contexts = self._load_item_contexts(bundle_root, self._manifest.eval_split)
        if max_items:
            items = items[:max_items]

        snapshot_id, composite = self._load_composite_snapshot(bundle_root)
        variant_dir = output_dir / variant.variant_id
        variant_dir.mkdir(parents=True, exist_ok=True)
        results_path = variant_dir / "results.json"

        results: list[BenchmarkResult] = []
        completed_ids: set[str] = set()
        if results_path.is_file():
            for row in json.loads(results_path.read_text(encoding="utf-8")):
                results.append(BenchmarkResult.model_validate(row))
                completed_ids.add(row["item_id"])
            if completed_ids:
                _progress(
                    f"Resuming {variant.variant_id}: {len(completed_ids)} items already scored"
                )
        pending_items = [item for item in items if item.item_id not in completed_ids]
        setup_mlflow()
        run_name = f"repro-{variant.variant_id}-{uuid.uuid4().hex[:8]}"
        variant_started = time.perf_counter()
        _progress(
            f"Starting variant {variant.variant_id}: {len(pending_items)} pending / "
            f"{len(items)} total (snapshot={snapshot_id})"
        )
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(
                {
                    "release_tag": self._manifest.release_tag,
                    "variant_id": variant.variant_id,
                    "custom_judge_version": self._manifest.custom_judge_version,
                }
            )
            parent_id = mlflow.active_run().info.run_id if mlflow.active_run() else ""

            if variant.backend == VariantBackend.FLAT_CHUNK:
                baseline = FlatChunkBaseline(
                    bundle_root=bundle_root,
                    variant=variant,
                )
                for idx, item in enumerate(pending_items, start=len(completed_ids) + 1):
                    item_started = time.perf_counter()
                    _progress(f"  [{variant.variant_id}] {idx}/{len(items)} {item.item_id}")
                    results.append(
                        self._score_flat_chunk_item(item, baseline, contexts.get(item.item_id))
                    )
                    _write_variant_results(results_path, results)
                    elapsed = time.perf_counter() - item_started
                    _progress(f"    done in {elapsed:.0f}s")
            else:
                graph_api = InMemoryGraphQueryAPI(composite)
                svc = QueryService(graph_api=graph_api, issuer_id=composite.issuer_id)
                caps = variant.capabilities
                for idx, item in enumerate(pending_items, start=len(completed_ids) + 1):
                    item_started = time.perf_counter()
                    _progress(f"  [{variant.variant_id}] {idx}/{len(items)} {item.item_id}")
                    results.append(
                        self._score_graph_item(
                            item,
                            svc,
                            snapshot_id,
                            composite.issuer_id,
                            caps,
                            contexts.get(item.item_id),
                            composite=composite,
                        )
                    )
                    _write_variant_results(results_path, results)
                    elapsed = time.perf_counter() - item_started
                    _progress(f"    done in {elapsed:.0f}s")

        variant_dir = output_dir / variant.variant_id
        report_dir = variant_dir / f"benchmark-{uuid.uuid4().hex[:8]}"
        report_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "variant_id": variant.variant_id,
            "item_count": len(results),
            "mean_outcome": _mean(results, "outcome_score"),
        }
        (report_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        incomplete = sum(
            1
            for r in results
            if (r.validation_status or "").lower() in {"incomplete", "non_reproducible"}
        )
        degraded = sum(1 for r in results if r.judge_status == "degraded")
        ref = EvalRunRef(
            variant_id=variant.variant_id,
            mlflow_parent_run_id=parent_id or "",
            report_dir=str(report_dir),
            items_excluded_incomplete=incomplete,
            items_excluded_degraded=degraded,
        )
        _write_variant_results(results_path, results)
        variant_elapsed = time.perf_counter() - variant_started
        _progress(
            f"Finished variant {variant.variant_id}: {len(results)} items in "
            f"{variant_elapsed / 60:.1f} min"
        )
        return results, ref

    def _score_flat_chunk_item(
        self,
        item: BenchmarkItem,
        baseline: FlatChunkBaseline,
        ctx: ItemContext | None,
    ) -> BenchmarkResult:
        chunk_ids, answer = baseline.answer(item.question)
        ranking = compute_ranking_metrics(
            chunk_ids,
            item.relevant_chunk_ids or (ctx.relevant_chunk_ids if ctx else []),
        )
        trajectory = build_trajectory_from_state({"evidence_chunks": answer.citations})
        verdict = self._judge.judge(item, answer, trajectory)
        traj_score = trajectory_fidelity_score(trajectory, judge_score=verdict.scores.get("trajectory_fidelity"))
        return BenchmarkResult(
            item_id=item.item_id,
            answer=answer,
            validation_status="complete",
            judge_status="ok",
            outcome_score=verdict.scores.get("synthesis_grounding", verdict.scores.get("value_alignment", 0)),
            alignment_score=verdict.scores.get("claim_presence", 0),
            trajectory_fidelity=traj_score,
            ranking_metrics=ranking,
            judge_verdict=verdict,
        )

    def _score_graph_item(
        self,
        item: BenchmarkItem,
        svc: QueryService,
        snapshot_id: str,
        issuer: str,
        caps,
        ctx: ItemContext | None,
        *,
        composite: GraphSnapshot,
    ) -> BenchmarkResult:
        pre_bound = []
        if item.expected_bindings and item.expected_bindings.accessions:
            acc_set = set(item.expected_bindings.accessions)
            pre_bound = [
                r for r in composite.manifest.filing_refs if r.accession in acc_set
            ]

        metadata = {
            "issuer_id": issuer,
            "benchmark_item": item.item_id,
            "expected_section_paths": json.dumps(item.expected_section_paths or []),
            "variant_disable_macro_router": str(caps.disable_macro_router).lower(),
            "variant_disable_graph_walker": str(caps.disable_graph_walker).lower(),
            "variant_xbrl_only": str(caps.xbrl_only).lower(),
            "cli_prebound": "true" if caps.disable_macro_router and pre_bound else "false",
            "trace_level": "quiet",
        }
        resp = svc.answer(
            QueryRequest(
                query=item.question,
                snapshot_id=snapshot_id,
                pre_bound_filings=pre_bound,
                metadata=metadata,
            )
        )
        citations = resp.answer.citations if resp.answer else []
        retrieved = [c.chunk_node_id for c in citations]
        ranking = compute_ranking_metrics(
            retrieved,
            item.relevant_chunk_ids or (ctx.relevant_chunk_ids if ctx else []),
        )
        trajectory = build_trajectory_from_state(
            {"evidence_chunks": citations, "query": item.question}
        )
        if resp.judge_scores:
            from models.evaluation import JudgeCriterionResult, JudgeVerdict

            verdict = JudgeVerdict(
                judge_model=resp.judge_status or "ask-audit",
                judge_version="ask-audit",
                rationale=resp.validation_status,
                scores=resp.judge_scores,
                criteria=[
                    JudgeCriterionResult(criterion_id=k, score=v, justification="ask audit")
                    for k, v in resp.judge_scores.items()
                ],
            )
        else:
            verdict = self._judge.judge(item, resp.answer, trajectory)
        traj_score = trajectory_fidelity_score(
            trajectory, judge_score=verdict.scores.get("trajectory_fidelity")
        )
        return BenchmarkResult(
            item_id=item.item_id,
            answer=resp.answer,
            mlflow_run_id=resp.mlflow_run_id,
            validation_status=resp.validation_status or "complete",
            judge_status=resp.judge_status or "ok",
            outcome_score=verdict.scores.get("synthesis_grounding", verdict.scores.get("value_alignment", 0)),
            alignment_score=verdict.scores.get("claim_presence", 0),
            trajectory_fidelity=traj_score,
            ranking_metrics=ranking,
            judge_verdict=verdict,
        )

    def run_all(
        self,
        *,
        output_dir: Path,
        max_items: int | None = None,
        skip_relevance: bool = False,
        strict_git: bool = False,
    ) -> ReproRun:
        _require_live_eval(self._manifest.release_tag)
        if strict_git:
            import subprocess

            head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            if head != self._manifest.git_sha and self._manifest.git_sha != "TBD":
                msg = f"git SHA mismatch: HEAD={head} manifest={self._manifest.git_sha}"
                raise RuntimeError(msg)

        self.verify_corpus()
        bundle = self._repo_root / self._manifest.custom_judge_bundle_path
        output_dir.mkdir(parents=True, exist_ok=True)
        if not skip_relevance and not self._relevance_ready(bundle):
            _progress("Materializing relevance labels...")
            self.materialize_relevance()
        elif self._relevance_ready(bundle):
            _progress("Relevance labels already present; skipping materialize")

        repro = ReproRun(
            repro_run_id=str(uuid.uuid4()),
            release_tag=self._manifest.release_tag,
            manifest_hash=sha256_file(self._manifest_path),
            offline_mode=True,
        )
        variants = resolve_variant_configs(self._manifest)
        contexts = self._load_item_contexts(bundle, self._manifest.eval_split)
        summaries = []

        for variant in variants:
            results, ref = self.run_variant(variant, max_items=max_items, output_dir=output_dir)
            repro.variant_runs.append(ref)
            profiles = {item_id: ctx.inspiration_profile for item_id, ctx in contexts.items()}
            gt = {item_id: ctx.ground_truth for item_id, ctx in contexts.items()}
            rel = {item_id: ctx.relevant_chunk_ids for item_id, ctx in contexts.items()}
            summaries.append(
                build_variant_summary(
                    variant.variant_id,
                    results,
                    profiles,
                    rel,
                    gt,
                )
            )

        export = export_paper_tables(summaries, release_tag=self._manifest.release_tag)
        write_paper_tables(export, output_dir)
        repro.completed_at = datetime.now(UTC)
        repro.status = "completed"
        (output_dir / "repro_run.json").write_text(repro.model_dump_json(indent=2), encoding="utf-8")

        expected = load_expected_checksums(self._manifest_path, self._manifest)
        if expected:
            verify = verify_tables(self._manifest, output_dir / "tables", expected)
            if not verify.ok:
                repro.status = "failed"
                raise RuntimeError(verify.message)
        return repro

    @staticmethod
    def _load_item_contexts(bundle_root: Path, split: str) -> dict[str, ItemContext]:
        path = bundle_root / "items" / f"{split}.jsonl"
        contexts: dict[str, ItemContext] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            gt = row.get("ground_truth") or {}
            contexts[row["item_id"]] = ItemContext(
                inspiration_profile=row.get("inspiration_profile", "unknown"),
                ground_truth=gt,
                relevant_chunk_ids=row.get("relevant_chunk_ids") or gt.get("relevant_chunk_ids") or [],
            )
        return contexts


def _mean(results: list[BenchmarkResult], field: str) -> float:
    vals = [getattr(r, field) for r in results]
    return sum(vals) / len(vals) if vals else 0.0
