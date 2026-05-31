"""Judge-assisted benchmark item generation (011)."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import httpx

from evaluation.generation.deduplicator import deduplicate_items
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.governance import BudgetTracker
from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.judges.gemini_panel import JudgeParseError
from models.benchmark_generation import (
    GeneratedBenchmarkItem,
    GenerationConfig,
    GenerationReport,
    SamplingManifest,
)
from models.enums import OperationClass
from models.evaluation import ExpectedBindings, GroundTruth

if TYPE_CHECKING:
    pass


class ItemGenerationTracer(Protocol):
    def item_start(self, seq: int, profile: str) -> None: ...
    def item_end(self, item_id: str, status: str, errors: list[str] | None = None) -> None: ...
    def gemini_call(
        self,
        *,
        profile: str,
        attempt: int,
        model: str,
        duration_ms: int,
        preview: str = "",
    ) -> None: ...
    def budget(self, message: str) -> None: ...
    def log(self, message: str) -> None: ...


def _profile_schedule(config: GenerationConfig, count: int, seed: int) -> list[str]:
    profiles = list(config.profile_quotas.keys())
    weights = [max(config.profile_quotas[p], 0.0) for p in profiles]
    if sum(weights) <= 0:
        msg = "profile_quotas must include at least one positive weight"
        raise ValueError(msg)
    rng = random.Random(seed)
    return rng.choices(profiles, weights=weights, k=count)


def _mock_item(
    *,
    profile: str,
    seq: int,
    accessions: list[str],
    section_paths: list[str],
) -> GeneratedBenchmarkItem:
    acc = accessions[0] if accessions else "unknown"
    path = section_paths[0] if section_paths else f"{acc}/Item7"
    multi = profile == "finagentbench"
    bindings = accessions if multi and len(accessions) >= 2 else [acc]
    if multi and len(bindings) < 2 and len(accessions) >= 2:
        bindings = accessions[:2]
    return GeneratedBenchmarkItem(
        item_id=f"mock-{profile}-{seq:03d}",
        question=f"Mock {profile} question #{seq} about filings {', '.join(bindings)}?",
        question_type_tag=f"{profile}-mock",
        inspiration_profile=profile,  # type: ignore[arg-type]
        ground_truth=GroundTruth(
            answer=f"mock answer {seq}" if profile != "finder" else None,
            rubric="Mock rubric" if profile == "finder" else None,
        ),
        expected_bindings=ExpectedBindings(accessions=bindings, fiscal_periods=[]),
        expected_section_paths=[path] if not multi else section_paths[:2] or [path],
        multi_filing_required=multi,
        operation_class=OperationClass.QUALITATIVE,
    )


def _use_mock_judge() -> bool:
    return os.environ.get("USE_MOCK_JUDGE", "0").strip().lower() in {"1", "true", "yes"}


def _load_checkpoint(checkpoint_path: Path) -> list[GeneratedBenchmarkItem]:
    if not checkpoint_path.is_file():
        return []
    rows: list[GeneratedBenchmarkItem] = []
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(GeneratedBenchmarkItem.model_validate(json.loads(line)))
    return rows


def _rewrite_checkpoint(checkpoint_path: Path, items: list[GeneratedBenchmarkItem]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.model_dump_json() + "\n")


def _append_checkpoint(checkpoint_path: Path, item: GeneratedBenchmarkItem) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as handle:
        handle.write(item.model_dump_json() + "\n")


def generate_items(
    config: GenerationConfig,
    sampling: SamplingManifest,
    draft_dir: Path,
    *,
    repo_root: Path | None = None,
    target_count: int | None = None,
    tracer: ItemGenerationTracer | None = None,
) -> tuple[list[GeneratedBenchmarkItem], GenerationReport]:
    started = time.perf_counter()
    index_path = draft_dir / "corpus" / "graph_node_index.json"
    graph_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    snapshot_accessions = {
        acc for issuer in sampling.selected_issuers for acc in issuer.accessions
    }
    if not graph_paths and snapshot_accessions:
        graph_paths = {f"{acc}/Item7" for acc in snapshot_accessions}

    count = (
        config.governance.max_items
        if target_count is None
        else min(target_count, config.governance.max_items)
    )
    schedule = _profile_schedule(config, count, config.random_seed + 1)
    budget = BudgetTracker(config.governance)
    use_mock = _use_mock_judge()
    live_generator = None if use_mock else GeminiItemGenerator(config, repo_root=repo_root)

    checkpoint_path = draft_dir / "candidates.jsonl"
    existing = _load_checkpoint(checkpoint_path)
    resumed = len(existing)
    if resumed >= count:
        if tracer:
            tracer.budget(f"checkpoint complete ({resumed}/{count}); skipping generation")
        accepted, rejected = deduplicate_items(
            existing,
            threshold=config.governance.dedup_similarity_threshold,
        )
        _rewrite_checkpoint(checkpoint_path, accepted + rejected)
        total = len(existing)
        accepted_count = len(accepted)
        return accepted, GenerationReport(
            run_id=draft_dir.name,
            candidates_total=total,
            accepted_count=accepted_count,
            rejected_count=len(rejected),
            pass_rate=accepted_count / total if total else 0.0,
            rejections_by_reason={},
            judge_api_calls=0,
            storage_bytes_used=0,
            duration_seconds=time.perf_counter() - started,
            budget_exceeded=False,
        )

    remaining_schedule = schedule[resumed:]
    candidates: list[GeneratedBenchmarkItem] = list(existing)
    seq = resumed + 1
    sorted_paths = sorted(graph_paths)
    accessions: list[str] = []
    for issuer in sampling.selected_issuers:
        accessions.extend(issuer.accessions)

    if tracer:
        mode = "mock" if use_mock else (live_generator.model_name if live_generator else "live")
        resume_note = f" resume_from={resumed + 1}" if resumed else ""
        tracer.budget(
            f"mode={mode} planned_items={count} remaining={len(remaining_schedule)}"
            f"{resume_note} graph_paths={len(graph_paths)}"
        )

    generated_this_run = 0
    for profile in remaining_schedule:
        budget.record_judge_call()
        budget.record_item()
        if tracer:
            tracer.item_start(seq, profile)

        validated: GeneratedBenchmarkItem | None = None
        feedback: str | None = None
        max_attempts = 1 if use_mock else config.governance.judge_retries_per_item + 1

        for attempt in range(max_attempts):
            try:
                if use_mock:
                    item = _mock_item(
                        profile=profile,
                        seq=seq,
                        accessions=accessions,
                        section_paths=sorted_paths,
                    )
                    duration_ms = 0
                else:
                    assert live_generator is not None
                    item, duration_ms = live_generator.generate_one(
                        profile=profile,
                        seq=seq,
                        sampling=sampling,
                        section_paths=sorted_paths,
                        validation_feedback=feedback,
                    )
                    if tracer:
                        tracer.gemini_call(
                            profile=profile,
                            attempt=attempt,
                            model=live_generator.model_name,
                            duration_ms=duration_ms,
                        )
                validated = validate_item(
                    item,
                    graph_paths=graph_paths,
                    snapshot_accessions=snapshot_accessions,
                )
                if validated.validation_status == "accepted":
                    break
                feedback = "; ".join(validated.validation_errors)
            except (JudgeParseError, RuntimeError, ValueError, httpx.HTTPError) as exc:
                feedback = str(exc)
                if attempt + 1 >= max_attempts:
                    validated = GeneratedBenchmarkItem(
                        item_id=f"failed-{profile}-{seq:03d}",
                        question="",
                        question_type_tag=f"{profile}-failed",
                        inspiration_profile=profile,  # type: ignore[arg-type]
                        ground_truth=GroundTruth(),
                        expected_bindings=ExpectedBindings(),
                        expected_section_paths=[],
                        validation_status="rejected",
                        validation_errors=[feedback],
                    )

        assert validated is not None
        if tracer:
            tracer.item_end(
                validated.item_id,
                validated.validation_status,
                validated.validation_errors or None,
            )
            if validated.question:
                tracer.log(f"    Q: {validated.question[:120]}")
        candidates.append(validated)
        _append_checkpoint(checkpoint_path, validated)
        generated_this_run += 1
        seq += 1

    accepted, rejected = deduplicate_items(
        candidates,
        threshold=config.governance.dedup_similarity_threshold,
    )
    _rewrite_checkpoint(checkpoint_path, accepted + rejected)

    total = len(candidates)
    accepted_count = len(accepted)
    rejected_count = len(rejected)
    pass_rate = accepted_count / total if total else 0.0
    rejections: dict[str, int] = {}
    for item in rejected:
        for code in item.validation_errors:
            rejections[code] = rejections.get(code, 0) + 1

    report = GenerationReport(
        run_id=draft_dir.name,
        candidates_total=total,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        pass_rate=pass_rate,
        rejections_by_reason=rejections,
        judge_api_calls=budget.judge_api_calls,
        storage_bytes_used=0,
        duration_seconds=time.perf_counter() - started,
        budget_exceeded=False,
    )
    if tracer and resumed:
        tracer.budget(
            f"resumed={resumed} generated_this_run={generated_this_run} total={total}"
        )
    return accepted, report


def write_items_jsonl(items: list[GeneratedBenchmarkItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in sorted(items, key=lambda i: i.item_id):
            handle.write(item.model_dump_json() + "\n")
