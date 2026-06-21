"""Multi-variant reproduction runner (012/013)."""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import mlflow

from contracts.query import QueryRequest
from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.generation.review._paths import resolve_release_bundle
from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.judges.outcome_scoring import compute_outcome_scores
from evaluation.metrics.ranking import compute_ranking_metrics
from evaluation.metrics.trajectory import trajectory_fidelity_score
from evaluation.reproduction.accession_index import AccessionIndex
from evaluation.reproduction.corpus_verify import (
    dry_run_registry_check,
    verify_bundle_pins,
    verify_corpus_hashes,
)
from evaluation.reproduction.defer_config import resolve_defer_config
from evaluation.reproduction.errors import MissingBindingsError
from evaluation.reproduction.export import (
    ItemContext,
    build_variant_summary,
    export_paper_tables,
    export_tables_from_disk,
    item_context_lookup_maps,
    load_item_contexts,
    write_paper_tables,
)
from evaluation.reproduction.flat_chunk import FlatChunkBaseline
from evaluation.reproduction.io import write_json_atomic
from evaluation.reproduction.judge_batch import run_judge_batch
from evaluation.reproduction.manifest import (
    load_expected_checksums,
    load_release_manifest,
    resolve_variant_configs,
    sha256_file,
)
from evaluation.reproduction.relevance import materialize_relevance_labels
from evaluation.reproduction.result_write import prepare_result_for_write, ungrounded_numeric_tokens
from evaluation.reproduction.snapshot_loader import load_item_subgraph
from evaluation.reproduction.structural import aggregate_structural_metrics
from evaluation.reproduction.structural_extract import build_structural_inputs
from evaluation.reproduction.verify_tables import verify_tables
from graph.query_api import InMemoryGraphQueryAPI
from models.evaluation import BenchmarkItem, BenchmarkResult, JudgeStatus
from models.graph import GraphSnapshot
from models.reproduction import (
    DeferJudgeConfig,
    EvalRunRef,
    ReleaseManifest,
    ReproRun,
    SystemVariantConfig,
    VariantBackend,
)
from retrieval.service import QueryService
from tracing.mlflow_langgraph import build_trajectory_from_state, setup_mlflow

_LIVE_EVAL_RELEASE_TAGS = frozenset({"paper-v1.0", "paper-live-smoke"})


def _require_live_eval(release_tag: str, *, defer: DeferJudgeConfig) -> None:
    if release_tag not in _LIVE_EVAL_RELEASE_TAGS:
        return
    if defer.enabled:
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


def _progress(message: str) -> None:
    print(message, flush=True)


def _write_variant_results(path: Path, results: list[BenchmarkResult]) -> None:
    prepared = [prepare_result_for_write(r) for r in results]
    write_json_atomic(path, [r.model_dump(mode="json") for r in prepared])


def _structural_metrics_for_variant(
    items: list[BenchmarkItem],
    results: list[BenchmarkResult],
):
    used, paths = build_structural_inputs(results)
    return aggregate_structural_metrics(
        items,
        used_accessions_by_item=used,
        visited_paths_by_item=paths,
    )


def _variant_is_complete(
    results: list[BenchmarkResult],
    planned_count: int,
    *,
    defer: bool,
) -> bool:
    if len(results) < planned_count:
        return False
    if defer and any((r.judge_status or "") == JudgeStatus.PENDING.value for r in results):
        return False
    return True


class ReproRunner:
    def __init__(
        self,
        manifest_path: Path,
        *,
        repo_root: Path | None = None,
        judge: GeminiJudgePanel | None = None,
        defer_config: DeferJudgeConfig | None = None,
    ) -> None:
        self._repo_root = repo_root or Path.cwd()
        self._manifest_path = manifest_path
        self._manifest = load_release_manifest(manifest_path)
        self._judge = judge or GeminiJudgePanel()
        self.defer_config = defer_config or resolve_defer_config()
        self._slice_cache: dict[frozenset[str], tuple[str, GraphSnapshot]] = {}
        self._accession_index: AccessionIndex | None = None

    @property
    def manifest(self) -> ReleaseManifest:
        return self._manifest

    def _bundle_root(self) -> Path:
        return resolve_release_bundle(
            self._repo_root,
            bundle_rel_path=self._manifest.custom_judge_bundle_path,
            version=self._manifest.custom_judge_version,
        )

    def _accession_index_for_bundle(self) -> AccessionIndex:
        if self._accession_index is None:
            self._accession_index = AccessionIndex.build(self._bundle_root())
        return self._accession_index

    def load_checkpoint(self, output_dir: Path) -> ReproRun | None:
        """Load repro_run.json checkpoint if present."""
        return self._load_repro_run(output_dir)

    def _load_repro_run(self, output_dir: Path) -> ReproRun | None:
        path = output_dir / "repro_run.json"
        if not path.is_file():
            return None
        return ReproRun.model_validate_json(path.read_text(encoding="utf-8"))

    def _save_repro_run(self, output_dir: Path, repro: ReproRun) -> None:
        write_json_atomic(output_dir / "repro_run.json", json.loads(repro.model_dump_json()))

    def verify_corpus(self) -> None:
        if os.environ.get("OFFLINE_BENCHMARK", "").strip() not in {"1", "true", "yes"}:
            msg = "OFFLINE_BENCHMARK=1 is required for reproduction"
            raise RuntimeError(msg)
        result = verify_corpus_hashes(self._manifest, repo_root=self._repo_root)
        if not result.ok:
            raise RuntimeError(result.message)
        pin_result = verify_bundle_pins(self._manifest, repo_root=self._repo_root)
        if not pin_result.ok:
            raise RuntimeError(pin_result.message)
        dry_run_registry_check(self._manifest, repo_root=self._repo_root)

    def materialize_relevance(self) -> None:
        materialize_relevance_labels(self._bundle_root(), split=self._manifest.eval_split)

    def _relevance_ready(self, bundle_root: Path) -> bool:
        sidecar = bundle_root / "relevance_labels.json"
        if not sidecar.is_file():
            return False
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return float(data.get("coverage_rate") or 0.0) >= 0.9

    def _item_slice(
        self,
        bundle_root: Path,
        item: BenchmarkItem,
    ) -> tuple[str, GraphSnapshot]:
        accessions: list[str] = []
        if item.expected_bindings and item.expected_bindings.accessions:
            accessions = list(item.expected_bindings.accessions)
        if not accessions:
            raise MissingBindingsError(item.item_id)
        key = frozenset(accessions)
        if key in self._slice_cache:
            return self._slice_cache[key]
        index = self._accession_index_for_bundle()
        slice_id, snapshot = load_item_subgraph(
            bundle_root,
            accessions,
            index,
            item_id=item.item_id,
        )
        self._slice_cache[key] = (slice_id, snapshot)
        return slice_id, snapshot

    def run_judge_batch_phase(
        self,
        output_dir: Path,
        *,
        variant_id: str | None = None,
        max_items: int | None = None,
    ) -> dict[str, int]:
        return run_judge_batch(
            output_dir,
            bundle_root=self._bundle_root(),
            split=self._manifest.eval_split,
            custom_judge_version=self._manifest.custom_judge_version,
            judge=self._judge,
            variant_id=variant_id,
            concurrency=self.defer_config.concurrency,
            max_items=max_items,
            progress=_progress,
        )

    def run_variant(
        self,
        variant: SystemVariantConfig,
        *,
        max_items: int | None = None,
        item_ids: list[str] | None = None,
        output_dir: Path,
        repro: ReproRun | None = None,
    ) -> tuple[list[BenchmarkResult], EvalRunRef]:
        bundle_root = self._bundle_root()
        ds = CustomJudgeDataset(
            version=self._manifest.custom_judge_version,
            bundle_root=bundle_root,
        )
        items = ds.load_split(self._manifest.eval_split)
        if item_ids:
            wanted = set(item_ids)
            items = [item for item in items if item.item_id in wanted]
            order = {iid: idx for idx, iid in enumerate(item_ids)}
            items.sort(key=lambda it: order.get(it.item_id, 9999))
        elif max_items:
            items = items[:max_items]
        contexts = load_item_contexts(bundle_root, self._manifest.eval_split)

        variant_dir = output_dir / variant.variant_id
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

        if _variant_is_complete(results, len(items), defer=self.defer_config.enabled):
            _progress(f"Skipping complete variant {variant.variant_id}")
            structural = _structural_metrics_for_variant(items, results)
            ref = EvalRunRef(
                variant_id=variant.variant_id,
                report_dir=str(variant_dir),
                structural_metrics=structural,
            )
            if repro is not None:
                repro.items_completed[variant.variant_id] = len(results)
                if variant.variant_id not in repro.completed_variants:
                    repro.completed_variants.append(variant.variant_id)
            return results, ref

        pending_items = [item for item in items if item.item_id not in completed_ids]
        setup_mlflow()
        run_name = f"repro-{variant.variant_id}-{uuid.uuid4().hex[:8]}"
        variant_started = time.perf_counter()
        if repro is not None:
            repro.current_variant = variant.variant_id
            self._save_repro_run(output_dir, repro)

        _progress(
            f"Starting variant {variant.variant_id}: {len(pending_items)} pending / "
            f"{len(items)} total (defer_judge={self.defer_config.enabled})"
        )
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(
                {
                    "release_tag": self._manifest.release_tag,
                    "variant_id": variant.variant_id,
                    "custom_judge_version": self._manifest.custom_judge_version,
                    "defer_judge": str(self.defer_config.enabled),
                }
            )
            parent_id = mlflow.active_run().info.run_id if mlflow.active_run() else ""

            if variant.backend == VariantBackend.FLAT_CHUNK:
                for idx, item in enumerate(pending_items, start=len(completed_ids) + 1):
                    item_started = time.perf_counter()
                    slice_id, slice_snap = self._item_slice(bundle_root, item)
                    accessions = (
                        list(item.expected_bindings.accessions)
                        if item.expected_bindings
                        else []
                    )
                    tickers = sorted(
                        {
                            self._accession_index_for_bundle().accession_to_issuer[a].ticker
                            for a in accessions
                        }
                    )
                    _progress(
                        f"  [{variant.variant_id}] {idx}/{len(items)} {item.item_id} "
                        f"issuers={tickers} nodes={len(slice_snap.nodes)} "
                        f"filings={len(slice_snap.manifest.filing_refs)}"
                    )
                    baseline = FlatChunkBaseline(
                        bundle_root=bundle_root,
                        variant=variant,
                        snapshot=slice_snap,
                    )
                    results.append(
                        self._score_flat_chunk_item(
                            item,
                            baseline,
                            contexts.get(item.item_id),
                            slice_id=slice_id,
                        )
                    )
                    _write_variant_results(results_path, results)
                    if repro is not None:
                        repro.items_completed[variant.variant_id] = len(results)
                        self._save_repro_run(output_dir, repro)
                    _progress(f"    done in {time.perf_counter() - item_started:.0f}s")
            else:
                caps = variant.capabilities
                for idx, item in enumerate(pending_items, start=len(completed_ids) + 1):
                    item_started = time.perf_counter()
                    slice_id, slice_snap = self._item_slice(bundle_root, item)
                    accessions = list(item.expected_bindings.accessions) if item.expected_bindings else []
                    tickers = sorted(
                        {
                            self._accession_index_for_bundle().accession_to_issuer[a].ticker
                            for a in accessions
                        }
                    )
                    _progress(
                        f"  [{variant.variant_id}] {idx}/{len(items)} {item.item_id} "
                        f"issuers={tickers} nodes={len(slice_snap.nodes)} "
                        f"filings={len(slice_snap.manifest.filing_refs)}"
                    )
                    graph_api = InMemoryGraphQueryAPI(slice_snap)
                    svc = QueryService(graph_api=graph_api, issuer_id=slice_snap.issuer_id)
                    scored = self._score_graph_item(
                        item,
                        svc,
                        slice_id,
                        slice_snap.issuer_id,
                        caps,
                        contexts.get(item.item_id),
                        snapshot=slice_snap,
                    )
                    if scored.answer and scored.answer.citations:
                        cited_text = " ".join(
                            getattr(c, "excerpt", "") or "" for c in scored.answer.citations
                        )
                        bad = ungrounded_numeric_tokens(scored.answer.text or "", cited_text)
                        if bad:
                            _progress(
                                f"    warn: ungrounded numeric tokens on {item.item_id}: "
                                f"{', '.join(bad[:3])}"
                            )
                    results.append(scored)
                    _write_variant_results(results_path, results)
                    if repro is not None:
                        repro.items_completed[variant.variant_id] = len(results)
                        self._save_repro_run(output_dir, repro)
                    from evaluation.reproduction.investigation.taxonomy import (
                        _synthesis_path,
                        extract_weakest_judge_criterion,
                    )

                    syn_path = _synthesis_path(scored)
                    cite_n = len(scored.answer.citations) if scored.answer else 0
                    weakest = extract_weakest_judge_criterion(scored)
                    outcome_val = float(scored.outcome_score or 0.0)
                    _progress(
                        f"[item={item.item_id} variant={variant.variant_id} "
                        f"synthesis_path={syn_path} citations={cite_n} "
                        f"outcome={outcome_val:.3f} weakest={weakest}]"
                    )
                    _progress(f"    done in {time.perf_counter() - item_started:.0f}s")

        if self.defer_config.enabled and self.defer_config.judge_after == "each_variant":
            _progress(f"Judge batch for {variant.variant_id}...")
            self.run_judge_batch_phase(output_dir, variant_id=variant.variant_id, max_items=max_items)
            results = [
                BenchmarkResult.model_validate(row)
                for row in json.loads(results_path.read_text(encoding="utf-8"))
            ]

        variant_dir.mkdir(parents=True, exist_ok=True)
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
        structural = _structural_metrics_for_variant(items, results)
        ref = EvalRunRef(
            variant_id=variant.variant_id,
            mlflow_parent_run_id=parent_id or "",
            report_dir=str(report_dir),
            items_excluded_incomplete=incomplete,
            items_excluded_degraded=degraded,
            structural_metrics=structural,
        )
        _write_variant_results(results_path, results)
        if repro is not None:
            repro.items_completed[variant.variant_id] = len(results)
            if _variant_is_complete(results, len(items), defer=self.defer_config.enabled):
                if variant.variant_id not in repro.completed_variants:
                    repro.completed_variants.append(variant.variant_id)
            self._save_repro_run(output_dir, repro)

        _progress(
            f"Finished variant {variant.variant_id}: {len(results)} items in "
            f"{(time.perf_counter() - variant_started) / 60:.1f} min"
        )
        return results, ref

    def _score_flat_chunk_item(
        self,
        item: BenchmarkItem,
        baseline: FlatChunkBaseline,
        ctx: ItemContext | None,
        *,
        slice_id: str = "",
    ) -> BenchmarkResult:
        chunk_ids, answer = baseline.answer(item.question)
        ranking = compute_ranking_metrics(
            chunk_ids,
            item.relevant_chunk_ids or (ctx.relevant_chunk_ids if ctx else []),
        )
        trajectory = build_trajectory_from_state({"evidence_chunks": answer.citations})
        if self.defer_config.enabled:
            return BenchmarkResult(
                item_id=item.item_id,
                answer=answer,
                validation_status="complete",
                judge_status=JudgeStatus.PENDING.value,
                trajectory_snapshot={"evidence_chunks": [c.model_dump(mode="json") for c in answer.citations], "query": item.question},
                ranking_metrics=ranking,
            )
        verdict = self._judge.judge(item, answer, trajectory)
        traj_score = trajectory_fidelity_score(
            trajectory, judge_score=verdict.scores.get("trajectory_fidelity")
        )
        outcome_score, alignment_score = compute_outcome_scores(item, answer, verdict)
        return BenchmarkResult(
            item_id=item.item_id,
            answer=answer,
            validation_status="complete",
            judge_status="ok",
            outcome_score=outcome_score,
            alignment_score=alignment_score,
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
        snapshot: GraphSnapshot,
    ) -> BenchmarkResult:
        pre_bound = []
        if item.expected_bindings and item.expected_bindings.accessions:
            acc_set = set(item.expected_bindings.accessions)
            pre_bound = [r for r in snapshot.manifest.filing_refs if r.accession in acc_set]

        temporal_anchor = ""
        if item.expected_bindings and item.expected_bindings.fiscal_periods:
            periods = list(item.expected_bindings.fiscal_periods)
            q_lower = item.question.lower()
            for period in periods:
                year = period[2:6] if period.startswith("FY") and len(period) >= 6 else ""
                if year and (year in q_lower or f"in {year}" in q_lower):
                    temporal_anchor = period
                    break
            if not temporal_anchor and periods:
                temporal_anchor = periods[0]

        metadata = {
            "issuer_id": issuer,
            "benchmark_item": item.item_id,
            "expected_section_paths": json.dumps(item.expected_section_paths or []),
            "variant_disable_macro_router": str(caps.disable_macro_router).lower(),
            "variant_disable_graph_walker": str(caps.disable_graph_walker).lower(),
            "variant_xbrl_only": str(caps.xbrl_only).lower(),
            "cli_prebound": "true" if pre_bound else "false",
            "temporal_anchor": temporal_anchor,
            "trace_level": "quiet",
            "defer_judge": "true" if self.defer_config.enabled else "false",
            "suppress_benchmark_path_injection": (
                "true" if item.suppress_benchmark_path_injection else "false"
            ),
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
        if self.defer_config.enabled or resp.judge_status == JudgeStatus.PENDING.value:
            return BenchmarkResult(
                item_id=item.item_id,
                answer=resp.answer,
                mlflow_run_id=resp.mlflow_run_id,
                generation_mlflow_run_id=resp.mlflow_run_id,
                validation_status=resp.validation_status or "complete",
                judge_status=JudgeStatus.PENDING.value,
                trajectory_snapshot=resp.trajectory_snapshot,
                ranking_metrics=ranking,
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
        outcome_score, alignment_score = compute_outcome_scores(item, resp.answer, verdict)
        return BenchmarkResult(
            item_id=item.item_id,
            answer=resp.answer,
            mlflow_run_id=resp.mlflow_run_id,
            validation_status=resp.validation_status or "complete",
            judge_status=resp.judge_status or "ok",
            outcome_score=outcome_score,
            alignment_score=alignment_score,
            trajectory_fidelity=traj_score,
            ranking_metrics=ranking,
            judge_verdict=verdict,
        )

    def run_all(
        self,
        *,
        output_dir: Path,
        max_items: int | None = None,
        item_ids: list[str] | None = None,
        skip_relevance: bool = False,
        strict_git: bool = False,
        resume: bool = True,
        export_only: bool = False,
        judge_only: bool = False,
        cli_defer: bool | None = None,
    ) -> ReproRun:
        if cli_defer is not None:
            self.defer_config = resolve_defer_config(cli_defer=cli_defer)

        from evaluation.reproduction.manifest import (
            enforce_full_repro_policy,
            enforce_max_items_policy,
        )

        variants = resolve_variant_configs(self._manifest)
        enforce_max_items_policy(self._manifest, max_items, item_ids=item_ids)
        enforce_full_repro_policy(
            self._manifest,
            max_items=max_items,
            item_ids=item_ids,
            variant_count=len(variants),
        )

        if export_only:
            export = export_tables_from_disk(
                output_dir,
                release_tag=self._manifest.release_tag,
                manifest=self._manifest,
                repo_root=self._repo_root,
            )
            write_paper_tables(export, output_dir)
            repro = self._load_repro_run(output_dir) or ReproRun(
                repro_run_id=str(uuid.uuid4()),
                release_tag=self._manifest.release_tag,
                manifest_hash=sha256_file(self._manifest_path),
                offline_mode=True,
            )
            repro.status = "completed"
            repro.completed_at = datetime.now(UTC)
            self._save_repro_run(output_dir, repro)
            return repro

        if judge_only:
            self.run_judge_batch_phase(output_dir, max_items=max_items)
            repro = self._load_repro_run(output_dir) or ReproRun(
                repro_run_id=str(uuid.uuid4()),
                release_tag=self._manifest.release_tag,
                manifest_hash=sha256_file(self._manifest_path),
                offline_mode=True,
                defer_judge=True,
            )
            repro.judge_phase_status = "complete"
            self._save_repro_run(output_dir, repro)
            return repro

        _require_live_eval(self._manifest.release_tag, defer=self.defer_config)
        if strict_git:
            import subprocess

            head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            pinned = (self._manifest.git_sha or "TBD").strip()
            if pinned not in {"TBD", ""} and head != pinned:
                msg = f"git SHA mismatch: HEAD={head} manifest={pinned}"
                raise RuntimeError(msg)
        elif (self._manifest.git_sha or "TBD").strip() not in {"TBD", ""}:
            import subprocess

            head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            pinned = self._manifest.git_sha.strip()
            if head != pinned:
                _progress(
                    f"Note: running from git {head[:12]} (manifest reference {pinned[:12]}); "
                    "data pins are verified separately"
                )

        if not resume and output_dir.exists():
            shutil.rmtree(output_dir)

        self.verify_corpus()
        bundle = self._bundle_root()
        output_dir.mkdir(parents=True, exist_ok=True)
        if not skip_relevance and not self._relevance_ready(bundle):
            _progress("Materializing relevance labels...")
            self.materialize_relevance()
        elif self._relevance_ready(bundle):
            _progress("Relevance labels already present; skipping materialize")

        repro = self._load_repro_run(output_dir) if resume else None
        if repro is None:
            repro = ReproRun(
                repro_run_id=str(uuid.uuid4()),
                release_tag=self._manifest.release_tag,
                manifest_hash=sha256_file(self._manifest_path),
                offline_mode=True,
                defer_judge=self.defer_config.enabled,
            )
        else:
            repro.defer_judge = self.defer_config.enabled

        variants = resolve_variant_configs(self._manifest)
        contexts = load_item_contexts(bundle, self._manifest.eval_split)
        profiles, rel, gt = item_context_lookup_maps(contexts)
        summaries = []

        for variant in variants:
            if resume and variant.variant_id in repro.completed_variants:
                _progress(f"Skipping completed variant {variant.variant_id} (checkpoint)")
                continue
            try:
                results, ref = self.run_variant(
                    variant,
                    max_items=max_items,
                    item_ids=item_ids,
                    output_dir=output_dir,
                    repro=repro,
                )
            except Exception as exc:
                repro.last_error = str(exc)
                repro.status = "failed"
                self._save_repro_run(output_dir, repro)
                raise
            repro.variant_runs.append(ref)
            summaries.append(
                build_variant_summary(
                    variant.variant_id,
                    results,
                    profiles,
                    rel,
                    gt,
                )
            )

        if self.defer_config.enabled and self.defer_config.judge_after == "all_variants":
            _progress("Judge batch (all variants)...")
            self.run_judge_batch_phase(output_dir, max_items=max_items)
            summaries = []
            for variant in variants:
                results_path = output_dir / variant.variant_id / "results.json"
                if not results_path.is_file():
                    continue
                results = [
                    BenchmarkResult.model_validate(row)
                    for row in json.loads(results_path.read_text(encoding="utf-8"))
                ]
                summaries.append(
                    build_variant_summary(
                        variant.variant_id,
                        results,
                        profiles,
                        rel,
                        gt,
                    )
                )

        if not summaries:
            for variant in variants:
                results_path = output_dir / variant.variant_id / "results.json"
                if not results_path.is_file():
                    continue
                results = [
                    BenchmarkResult.model_validate(row)
                    for row in json.loads(results_path.read_text(encoding="utf-8"))
                ]
                summaries.append(
                    build_variant_summary(
                        variant.variant_id,
                        results,
                        profiles,
                        rel,
                        gt,
                    )
                )

        has_pending = any(
            (r.judge_status or "") == JudgeStatus.PENDING.value
            for summary in summaries
            for rec in summary.records
            for r in [rec.result]
        )
        if has_pending and not self.defer_config.allow_pending_export:
            repro.judge_phase_status = "partial"
            repro.status = "running"
            self._save_repro_run(output_dir, repro)
            msg = "Judge phase incomplete; pending items remain (use --allow-pending-export or run judge-batch)"
            raise RuntimeError(msg)

        export = export_paper_tables(
            summaries,
            release_tag=self._manifest.release_tag,
            relevance_by_item=rel,
            custom_judge_version=self._manifest.custom_judge_version,
        )
        write_paper_tables(export, output_dir)
        repro.completed_at = datetime.now(UTC)
        repro.status = "completed"
        repro.judge_phase_status = "complete"
        repro.current_variant = ""
        self._save_repro_run(output_dir, repro)

        expected = load_expected_checksums(self._manifest_path, self._manifest)
        if expected:
            verify = verify_tables(self._manifest, output_dir / "tables", expected)
            if not verify.ok:
                repro.status = "failed"
                raise RuntimeError(verify.message)
        return repro

def _mean(results: list[BenchmarkResult], field: str) -> float:
    vals = [getattr(r, field) for r in results]
    return sum(vals) / len(vals) if vals else 0.0
