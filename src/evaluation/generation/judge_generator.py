"""Judge-assisted benchmark item generation (011)."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import httpx

from datetime import UTC, datetime

from evaluation.generation.deduplicator import deduplicate_items, find_duplicate_match
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.governance import BudgetTracker
from evaluation.generation.bundle_version import is_v2_or_later
from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.generation.v2_item_normalize import normalize_v2_item
from evaluation.generation.review.diversity import append_duplicate_feedback, write_diversity_report
from evaluation.judges.gemini_panel import JudgeParseError
from models.benchmark_generation import (
    DuplicateRejectionFeedback,
    GeneratedBenchmarkItem,
    GenerationConfig,
    GenerationReport,
    SamplingManifest,
)
from models.enums import OperationClass
from models.evaluation import ExpectedBindings, GroundTruth

if TYPE_CHECKING:
    pass

PUBLISH_MIN_ACCEPTED = 200


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


def _revalidate_candidates(
    items: list[GeneratedBenchmarkItem],
    *,
    graph_paths: set[str],
    snapshot_accessions: set[str],
    bundle_version: str | None = None,
) -> list[GeneratedBenchmarkItem]:
    v2 = is_v2_or_later(bundle_version or "")
    return [
        validate_item(
            normalize_v2_item(item) if v2 else item,
            graph_paths=graph_paths,
            snapshot_accessions=snapshot_accessions,
            bundle_version=bundle_version,
        )
        for item in items
    ]


def _min_unique_target(planned_count: int) -> int:
    if planned_count >= PUBLISH_MIN_ACCEPTED:
        return PUBLISH_MIN_ACCEPTED
    return planned_count


def _validation_pass_rate(candidates: list[GeneratedBenchmarkItem]) -> float:
    if not candidates:
        return 0.0
    validation_passed = sum(
        1
        for item in candidates
        if item.validation_status == "accepted"
        or "duplicate_question" in item.validation_errors
    )
    return validation_passed / len(candidates)


def _build_generation_report(
    *,
    run_id: str,
    candidates: list[GeneratedBenchmarkItem],
    accepted: list[GeneratedBenchmarkItem],
    rejected: list[GeneratedBenchmarkItem],
    judge_api_calls: int,
    started: float,
) -> GenerationReport:
    rejections: dict[str, int] = {}
    for item in rejected:
        for code in item.validation_errors:
            rejections[code] = rejections.get(code, 0) + 1
    return GenerationReport(
        run_id=run_id,
        candidates_total=len(candidates),
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        pass_rate=_validation_pass_rate(candidates),
        rejections_by_reason=rejections,
        judge_api_calls=judge_api_calls,
        storage_bytes_used=0,
        duration_seconds=time.perf_counter() - started,
        budget_exceeded=False,
    )


def _accession_to_ticker(sampling: SamplingManifest) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for issuer in sampling.selected_issuers:
        for acc in issuer.accessions:
            mapping[acc] = issuer.ticker
    return mapping


def _issuer_for_item(item: GeneratedBenchmarkItem, acc_to_ticker: dict[str, str]) -> str:
    accs = item.expected_bindings.accessions or []
    if not accs:
        return "unknown"
    return acc_to_ticker.get(accs[0], accs[0][:8])


def _blocked_tickers_for_profile(
    profile: str,
    issuer_counts: dict[tuple[str, str], int],
    *,
    cap: int,
) -> list[str]:
    blocked: list[str] = []
    for (prof, ticker), count in issuer_counts.items():
        if prof == profile and count >= cap:
            blocked.append(ticker)
    return sorted(set(blocked))


def _generate_one_candidate(
    *,
    profile: str,
    seq: int,
    use_mock: bool,
    live_generator: GeminiItemGenerator | None,
    config: GenerationConfig,
    sampling: SamplingManifest,
    sorted_paths: list[str],
    accessions: list[str],
    graph_paths: set[str],
    snapshot_accessions: set[str],
    tracer: ItemGenerationTracer | None,
    negative_questions: list[str] | None = None,
    blocked_tickers: list[str] | None = None,
) -> GeneratedBenchmarkItem:
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
                    negative_questions=negative_questions,
                    blocked_tickers=blocked_tickers,
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
                bundle_version=config.bundle_schema_version,
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
    return validated


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
    min_unique = _min_unique_target(count)
    schedule = _profile_schedule(config, count, config.random_seed + 1)
    budget = BudgetTracker(config.governance)
    use_mock = _use_mock_judge()
    live_generator = None if use_mock else GeminiItemGenerator(config, repo_root=repo_root)

    checkpoint_path = draft_dir / "candidates.jsonl"
    existing = _load_checkpoint(checkpoint_path)
    candidates = _revalidate_candidates(
        existing,
        graph_paths=graph_paths,
        snapshot_accessions=snapshot_accessions,
        bundle_version=config.bundle_schema_version,
    )
    if candidates and candidates != existing:
        _rewrite_checkpoint(checkpoint_path, candidates)
    resumed = len(existing)

    accepted, _ = deduplicate_items(
        candidates,
        threshold=config.governance.dedup_similarity_threshold,
    )
    if len(accepted) >= min_unique:
        if tracer:
            tracer.budget(
                f"checkpoint complete ({len(accepted)} unique accepted / {min_unique} required);"
                " skipping generation"
            )
        accepted, rejected = deduplicate_items(
            candidates,
            threshold=config.governance.dedup_similarity_threshold,
        )
        _rewrite_checkpoint(checkpoint_path, accepted + rejected)
        return accepted, _build_generation_report(
            run_id=draft_dir.name,
            candidates=candidates,
            accepted=accepted,
            rejected=rejected,
            judge_api_calls=0,
            started=started,
        )

    schedule_index = len(candidates)
    seq = len(candidates) + 1
    sorted_paths = sorted(graph_paths)
    accessions: list[str] = []
    for issuer in sampling.selected_issuers:
        accessions.extend(issuer.accessions)
    acc_to_ticker = _accession_to_ticker(sampling)
    issuer_accept_counts: dict[tuple[str, str], int] = {}
    issuer_cap = config.governance.max_items_per_issuer_per_profile
    neg_example_count = config.governance.prompt_negative_examples_count

    if tracer:
        mode = "mock" if use_mock else (live_generator.model_name if live_generator else "live")
        resume_note = f" resume_from={resumed + 1}" if resumed else ""
        tracer.budget(
            f"mode={mode} planned_items={count} min_unique={min_unique}"
            f" accepted={len(accepted)}{resume_note} graph_paths={len(graph_paths)}"
        )

    generated_this_run = 0
    dedup_threshold = config.governance.dedup_similarity_threshold
    max_calls = config.governance.max_judge_api_calls
    publish_oriented = min_unique >= PUBLISH_MIN_ACCEPTED
    unique_accepted, _ = deduplicate_items(
        [item for item in candidates if item.validation_status == "accepted"],
        threshold=dedup_threshold,
    )

    while True:
        if publish_oriented:
            if len(unique_accepted) >= min_unique or budget.judge_api_calls >= max_calls:
                break
        elif len(candidates) >= count or budget.judge_api_calls >= max_calls:
            break

        if schedule_index >= len(schedule):
            if not publish_oriented:
                break
            schedule.extend(
                _profile_schedule(
                    config,
                    count,
                    config.random_seed + 1000 + schedule_index,
                )
            )
        profile = schedule[schedule_index]
        schedule_index += 1

        budget.record_judge_call()
        if not publish_oriented or len(candidates) < count:
            budget.record_item()
        if tracer:
            tracer.item_start(seq, profile)

        negative_qs = [
            item.question
            for item in reversed(unique_accepted)
            if item.inspiration_profile == profile
        ][:neg_example_count]
        blocked = _blocked_tickers_for_profile(profile, issuer_accept_counts, cap=issuer_cap)

        validated = _generate_one_candidate(
            profile=profile,
            seq=seq,
            use_mock=use_mock,
            live_generator=live_generator,
            config=config,
            sampling=sampling,
            sorted_paths=sorted_paths,
            accessions=accessions,
            graph_paths=graph_paths,
            snapshot_accessions=snapshot_accessions,
            tracer=tracer,
            negative_questions=negative_qs or None,
            blocked_tickers=blocked or None,
        )

        if validated.validation_status == "accepted":
            matched, sim_score = find_duplicate_match(
                validated,
                unique_accepted,
                threshold=dedup_threshold,
            )
            if matched is not None:
                validated = validated.model_copy(
                    update={
                        "validation_status": "rejected",
                        "validation_errors": [
                            *validated.validation_errors,
                            "duplicate_question",
                        ],
                    }
                )
                if config.governance.duplicate_feedback_enabled:
                    append_duplicate_feedback(
                        draft_dir,
                        DuplicateRejectionFeedback(
                            rejected_question=validated.question,
                            matched_item_id=matched.item_id,
                            inspiration_profile=profile,
                            issuer_ticker=_issuer_for_item(validated, acc_to_ticker),
                            similarity_score=sim_score,
                            rejected_at=datetime.now(UTC),
                        ),
                    )
            else:
                ticker = _issuer_for_item(validated, acc_to_ticker)
                key = (profile, ticker)
                if issuer_accept_counts.get(key, 0) >= issuer_cap:
                    validated = validated.model_copy(
                        update={
                            "validation_status": "rejected",
                            "validation_errors": [
                                *validated.validation_errors,
                                "issuer_cap_exceeded",
                            ],
                        }
                    )
                else:
                    unique_accepted.append(validated)
                    issuer_accept_counts[key] = issuer_accept_counts.get(key, 0) + 1

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
        threshold=dedup_threshold,
    )
    _rewrite_checkpoint(checkpoint_path, accepted + rejected)

    report = _build_generation_report(
        run_id=draft_dir.name,
        candidates=candidates,
        accepted=accepted,
        rejected=rejected,
        judge_api_calls=budget.judge_api_calls,
        started=started,
    )
    write_diversity_report(draft_dir)
    if tracer and resumed:
        tracer.budget(
            f"resumed={resumed} generated_this_run={generated_this_run} total={len(candidates)}"
        )
    return accepted, report


def write_items_jsonl(items: list[GeneratedBenchmarkItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in sorted(items, key=lambda i: i.item_id):
            handle.write(item.model_dump_json() + "\n")
