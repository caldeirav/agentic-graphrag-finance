"""Draft and published bundle assembly for custom-judge datasets (011).

Extend workflow: parent published artifacts are immutable. ``extend`` copies parent
items/corpus into a new draft; delta issuers may add a new composite ``snapshot_id``
while reusing unchanged parent issuer snapshots when filings overlap.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from evaluation.generation.comparison_gt import (
    comparison_answer_informativeness_score,
    is_boilerplate_comparison_answer,
    is_comparison_item,
    validate_comparison_structured,
)
from evaluation.generation.bundle_version import is_v2_bundle, is_v2_or_later
from evaluation.generation.feasibility_macro import audit_macro_bindability
from evaluation.generation.profile_selection import (
    quota_targets,
    select_profile_balanced_items,
    selection_report,
)
from evaluation.generation.gt_classifier import is_numeric_answer_gt
from evaluation.generation.item_validator import load_graph_paths
from evaluation.generation.section_paths import resolve_section_paths
from models.benchmark_generation import (
    AnswerType,
    CorpusBundle,
    DatasetManifest,
    DatasetStatus,
    GeneratedBenchmarkItem,
    GenerationConfig,
    GenerationReport,
    SamplingManifest,
)


def items_hash(items_path: Path) -> str:
    lines = [
        line.strip()
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [json.loads(line) for line in lines]
    rows.sort(key=lambda r: r["item_id"])
    body = "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def profile_counts(items: list[GeneratedBenchmarkItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.inspiration_profile] = counts.get(item.inspiration_profile, 0) + 1
    return counts


def write_draft_manifest(
    *,
    draft_dir: Path,
    config: GenerationConfig,
    sampling: SamplingManifest,
    bundle: CorpusBundle,
    report: GenerationReport,
    items_path: Path,
    version: str = "0.0.0-draft",
) -> DatasetManifest:
    manifest = DatasetManifest(
        schema_version=config.bundle_schema_version,
        version=version,
        status=DatasetStatus.DRAFT,
        item_count=len([ln for ln in items_path.read_text().splitlines() if ln.strip()]),
        items_hash=items_hash(items_path),
        sampling_manifest_path="sampling_manifest.json",
        generation_config_path="generation_config.yaml",
        generation_report_path="generation_report.json",
        corpus_bundle=bundle,
        generation_judge_version=config.generation_judge_version,
        evaluation_judge_version=config.evaluation_judge_version,
        profile_counts=profile_counts(
            [
                GeneratedBenchmarkItem.model_validate(json.loads(line))
                for line in items_path.read_text().splitlines()
                if line.strip()
            ]
        ),
    )
    (draft_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (draft_dir / "generation_config.yaml").write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    )
    (draft_dir / "generation_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n"
    )
    return manifest


def _comparison_tag(tag: str) -> bool:
    lowered = (tag or "").lower()
    return any(kw in lowered for kw in ("comparison", "multi-hop", "cross-filing", "agentic-multi"))


def _reference_tag(tag: str) -> bool:
    return "reference" in (tag or "").lower()


def _corpus_accessions(bundle_root: Path) -> set[str]:
    index_path = bundle_root / manifest_corpus_index_path(bundle_root)
    if not index_path.is_file():
        return set()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    accessions: set[str] = set()
    for path in data.get("paths", []):
        acc = str(path).split("/")[0]
        if acc:
            accessions.add(acc)
    for key in ("accessions", "nodes"):
        for entry in data.get(key, []):
            if isinstance(entry, str):
                accessions.add(entry.split("/")[0])
    return accessions


def manifest_corpus_index_path(bundle_root: Path) -> Path:
    manifest_path = bundle_root / "manifest.json"
    if manifest_path.is_file():
        manifest = DatasetManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
        rel = manifest.corpus_bundle.graph_node_index_path
        return bundle_root / rel
    return bundle_root / "corpus" / "graph_node_index.json"


def _years_in_text(text: str) -> set[int]:
    return {int(y) for y in re.findall(r"20\d{2}", text or "")}


def _multi_filing_item(item: GeneratedBenchmarkItem) -> bool:
    if item.multi_filing_required:
        return True
    return _comparison_tag(item.question_type_tag)


def _v1_item_id(item_id: str) -> bool:
    """True when item_id matches v1.x live generation pattern (not v2 net-new pool)."""
    lowered = item_id.lower()
    if lowered.startswith("v2-"):
        return False
    return lowered.startswith("live-") or bool(re.match(r"^[a-z]+-\d{4}$", lowered))


def _validate_v2_item(item: GeneratedBenchmarkItem) -> list[dict[str, str]]:
    blocked: list[dict[str, str]] = []
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    if not answer:
        blocked.append(
            {
                "item_id": item.item_id,
                "reason": "missing_answer_gt",
                "detail": "v2 item requires non-empty ground_truth.answer",
            }
        )
    if _v1_item_id(item.item_id):
        blocked.append(
            {
                "item_id": item.item_id,
                "reason": "v1_item_reuse",
                "detail": "v2 bundle forbids v1.x item_id reuse",
            }
        )
    answer_type = item.answer_type
    if answer_type in (AnswerType.NARRATIVE, AnswerType.COMPARISON_STRUCTURED):
        claims = [c.strip() for c in (gt.required_claims or []) if c and c.strip()]
        min_claims = 3 if answer_type == AnswerType.COMPARISON_STRUCTURED else 2
        max_claims = 8
        if len(claims) < min_claims or len(claims) > max_claims:
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "required_claims",
                    "detail": f"expected {min_claims}-{max_claims} claims, got {len(claims)}",
                }
            )
    if is_comparison_item(item):
        if answer_type != AnswerType.COMPARISON_STRUCTURED:
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "invalid_answer_type",
                    "detail": "comparison item requires answer_type=comparison_structured",
                }
            )
        for code in validate_comparison_structured(item):
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": code,
                    "detail": f"comparison_structured validation failed: {code}",
                }
            )
    return blocked


def build_scorability_report(items: list[GeneratedBenchmarkItem]) -> dict[str, object]:
    by_answer_type: dict[str, int] = {}
    rubric_only = 0
    scorable = 0
    boilerplate_count = 0
    borderline_ids: list[str] = []
    for item in items:
        gt = item.ground_truth
        has_answer = bool((gt.answer or "").strip())
        has_rubric_only = bool((gt.rubric or "").strip()) and not has_answer
        if has_rubric_only:
            rubric_only += 1
        if has_answer:
            scorable += 1
        key = item.answer_type.value if item.answer_type else "unknown"
        by_answer_type[key] = by_answer_type.get(key, 0) + 1
        if is_comparison_item(item) and has_answer:
            answer = (gt.answer or "").strip()
            if is_boilerplate_comparison_answer(answer):
                boilerplate_count += 1
            elif comparison_answer_informativeness_score(answer) < 0.5:
                borderline_ids.append(item.item_id)
    return {
        "scorable_item_count": scorable,
        "item_count": len(items),
        "by_answer_type": by_answer_type,
        "rubric_only_count": rubric_only,
        "answer_gt_coverage": scorable / len(items) if items else 0.0,
        "boilerplate_comparison_count": boilerplate_count,
        "borderline_comparison_item_ids": sorted(borderline_ids),
    }


def write_scorability_report(bundle_root: Path, items_path: Path) -> Path:
    items = [
        GeneratedBenchmarkItem.model_validate(json.loads(line))
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = build_scorability_report(items)
    path = bundle_root / "scorability_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def question_binding_year_mismatch(item: GeneratedBenchmarkItem) -> tuple[bool, str]:
    """True when question cites a calendar/filing year absent from fiscal_periods."""
    q_years = _years_in_text(item.question)
    period_years: set[int] = set()
    for period in item.expected_bindings.fiscal_periods or []:
        period_years.update(_years_in_text(str(period)))
    if not q_years or not period_years:
        return False, ""
    if q_years & period_years:
        return False, ""
    extra = sorted(q_years - period_years)
    bound = sorted(period_years)
    return True, f"question years {extra} not in bindings {bound}"


def validate_section_reachability(
    bundle_root: Path,
    items_path: Path,
) -> dict[str, object]:
    """Audit answer-GT items for resolvable expected_section_paths in corpus index."""
    items = [
        GeneratedBenchmarkItem.model_validate(json.loads(line))
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    index_path = manifest_corpus_index_path(bundle_root)
    graph_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    corpus_accessions = _corpus_accessions(bundle_root)
    unreachable: list[dict[str, str]] = []
    for item in items:
        gt = item.ground_truth
        if not gt.answer:
            continue
        paths = list(item.expected_section_paths or [])
        if not paths:
            unreachable.append(
                {
                    "item_id": item.item_id,
                    "reason": "missing_section_paths",
                    "detail": "answer-GT item has no expected_section_paths",
                }
            )
            continue
        if not graph_paths:
            continue
        resolved, unresolved = resolve_section_paths(
            paths,
            graph_paths,
            snapshot_accessions=corpus_accessions,
        )
        if unresolved or not resolved:
            unreachable.append(
                {
                    "item_id": item.item_id,
                    "reason": "section_unreachable",
                    "detail": f"unresolved paths: {', '.join(unresolved or paths)}",
                }
            )
    return {
        "unreachable_answer_gt_count": len(unreachable),
        "unreachable_items": unreachable,
        "item_count": len(items),
    }


def validate_bundle_feasibility(
    bundle_root: Path,
    items_path: Path,
    *,
    manifest: DatasetManifest | None = None,
) -> dict[str, object]:
    """Return feasibility report; blocked items fail publish gates."""
    if manifest is None:
        manifest_path = bundle_root / "manifest.json"
        if manifest_path.is_file():
            manifest = DatasetManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
    items = [
        GeneratedBenchmarkItem.model_validate(json.loads(line))
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    v2 = manifest is not None and is_v2_bundle(manifest)
    bundle_version = manifest.version if manifest else None
    corpus_accessions = _corpus_accessions(bundle_root)
    blocked: list[dict[str, str]] = []
    multi_filing_count = 0
    for item in items:
        if v2:
            blocked.extend(_validate_v2_item(item))
        if _multi_filing_item(item):
            multi_filing_count += 1
        tag = item.question_type_tag
        accs = list(dict.fromkeys(item.expected_bindings.accessions))
        if _comparison_tag(tag) and len(accs) < 2:
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "comparison_bindings",
                    "detail": f"expected {len(accs)} accessions, need >= 2",
                }
            )
        if _reference_tag(tag) and accs:
            missing = [a for a in accs if a not in corpus_accessions]
            if missing and corpus_accessions:
                blocked.append(
                    {
                        "item_id": item.item_id,
                        "reason": "reference_corpus",
                        "detail": f"missing accessions: {', '.join(missing)}",
                    }
                )
        gt = item.ground_truth
        if not v2 and gt.answer and not is_numeric_answer_gt(gt.answer):
            claims = gt.required_claims or []
            if not claims:
                blocked.append(
                    {
                        "item_id": item.item_id,
                        "reason": "required_claims",
                        "detail": "narrative answer-GT missing required_claims",
                    }
                )
        if is_rubric_only_routing(item, bundle_version=bundle_version) and not (gt.rubric or "").strip():
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "rubric_route",
                    "detail": "rubric-only item missing rubric text",
                }
            )
        mismatched, detail = question_binding_year_mismatch(item)
        if gt.answer and mismatched:
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "question_binding_year_mismatch",
                    "detail": detail,
                }
            )
    reachability = validate_section_reachability(bundle_root, items_path)
    for entry in reachability["unreachable_items"]:  # type: ignore[union-attr]
        blocked.append(entry)
    macro_failures = 0
    if v2:
        macro_report = audit_macro_bindability(bundle_root, items)
        macro_failures = int(macro_report["macro_bindability_failures"])
        blocked.extend(macro_report["failures"])  # type: ignore[arg-type]
    scorability = build_scorability_report(items)
    return {
        "blocked_count": len(blocked),
        "blocked_items": blocked,
        "item_count": len(items),
        "year_mismatch_count": sum(
            1 for b in blocked if b["reason"] == "question_binding_year_mismatch"
        ),
        "unreachable_answer_gt_count": reachability["unreachable_answer_gt_count"],
        "macro_bindability_failures": macro_failures,
        "multi_filing_count": multi_filing_count,
        "answer_gt_coverage": scorability["answer_gt_coverage"],
    }


def is_rubric_only_routing(
    item: GeneratedBenchmarkItem,
    *,
    bundle_version: str | None = None,
) -> bool:
    if bundle_version and is_v2_or_later(bundle_version):
        return False
    if item.answer_type is not None:
        return False
    return _comparison_tag(item.question_type_tag) or _reference_tag(item.question_type_tag)


def load_dev_split_items(items_path: Path) -> list[GeneratedBenchmarkItem]:
    """Load accepted dev items from ``items/dev.jsonl``."""
    lines = [
        line.strip()
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [GeneratedBenchmarkItem.model_validate(json.loads(line)) for line in lines]


def load_dev_item_pool(bundle_root: Path) -> list[GeneratedBenchmarkItem]:
    """Load full accepted pool (``dev_pool.jsonl``) or current dev split."""
    pool_path = bundle_root / "items" / "dev_pool.jsonl"
    if pool_path.is_file():
        return load_dev_split_items(pool_path)
    return load_dev_split_items(bundle_root / "items" / "dev.jsonl")


def apply_profile_balanced_dev_split(
    bundle_root: Path,
    *,
    profile_quotas: dict[str, float],
    target_count: int,
    seed: int,
) -> dict[str, object]:
    """Write quota-balanced ``items/dev.jsonl`` from the accepted pool."""
    from evaluation.generation.judge_generator import write_items_jsonl

    pool = load_dev_item_pool(bundle_root)
    dev_path = bundle_root / "items" / "dev.jsonl"
    targets = quota_targets(profile_quotas, target_count)
    if len(pool) <= target_count:
        report = selection_report(
            pool_count=len(pool),
            selected=sorted(pool, key=lambda item: item.item_id),
            targets=targets,
            seed=seed,
        )
        report["skipped"] = True
        return report

    selected = select_profile_balanced_items(
        pool,
        profile_quotas,
        target_count,
        seed=seed,
    )
    write_items_jsonl(selected, dev_path)
    report = selection_report(
        pool_count=len(pool),
        selected=selected,
        targets=targets,
        seed=seed,
    )
    report["skipped"] = False
    (bundle_root / "dev_selection_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def check_publish_gates(
    manifest: DatasetManifest,
    report: GenerationReport,
    *,
    min_items: int = 200,
    min_pass_rate: float = 0.95,
    skip_gates: bool = False,
    bundle_root: Path | None = None,
    multi_filing_min: int = 0,
    require_publish_audit: bool = False,
) -> None:
    if skip_gates:
        return
    v2 = is_v2_bundle(manifest)
    if manifest.item_count < min_items:
        msg = f"Publish gate failed: item_count {manifest.item_count} < {min_items}"
        raise ValueError(msg)
    # v1.x: candidate validation pass rate is blocking. v2: dev.jsonl quality gates only;
    # generation_report.pass_rate is retained as an indicative yield metric.
    if not v2 and report.pass_rate < min_pass_rate:
        msg = f"Publish gate failed: pass_rate {report.pass_rate} < {min_pass_rate}"
        raise ValueError(msg)
    if bundle_root is not None:
        items_path = bundle_root / "items" / "dev.jsonl"
        if not items_path.is_file():
            msg = f"Publish gate failed: missing dev split at {items_path}"
            raise ValueError(msg)
        if v2:
            dev_items = load_dev_split_items(items_path)
            if len(dev_items) < min_items:
                msg = (
                    f"Publish gate failed: dev.jsonl has {len(dev_items)} items < {min_items}"
                )
                raise ValueError(msg)
            if len(dev_items) != manifest.item_count:
                msg = (
                    f"Publish gate failed: manifest item_count {manifest.item_count} "
                    f"!= dev.jsonl rows {len(dev_items)}"
                )
                raise ValueError(msg)
            write_scorability_report(bundle_root, items_path)
        if items_path.is_file():
            feasibility = validate_bundle_feasibility(bundle_root, items_path, manifest=manifest)
            blocked_count = int(feasibility["blocked_count"])
            if blocked_count > 0:
                first = feasibility["blocked_items"][0]  # type: ignore[index]
                msg = (
                    f"Publish gate failed: {blocked_count} infeasible item(s); "
                    f"first={first['item_id']} ({first['reason']})"
                )
                raise ValueError(msg)
            if v2:
                coverage = float(feasibility.get("answer_gt_coverage", 0.0))
                if coverage < 1.0:
                    msg = f"Publish gate failed: answer_gt_coverage {coverage} < 1.0"
                    raise ValueError(msg)
                scorability_path = bundle_root / "scorability_report.json"
                if scorability_path.is_file():
                    scorability = json.loads(scorability_path.read_text(encoding="utf-8"))
                    if int(scorability.get("rubric_only_count", 0)) > 0:
                        msg = "Publish gate failed: rubric_only_count must be 0 for v2 bundles"
                        raise ValueError(msg)
                    if int(scorability.get("boilerplate_comparison_count", 0)) > 0:
                        msg = (
                            "Publish gate failed: boilerplate_comparison_count must be 0 "
                            "for v2.0.1+ bundles"
                        )
                        raise ValueError(msg)
                if multi_filing_min >= 0:
                    floor = multi_filing_min if multi_filing_min > 0 else 40
                    mf_count = int(feasibility.get("multi_filing_count", 0))
                    if mf_count < floor:
                        msg = (
                            f"Publish gate failed: multi_filing_count {mf_count} < {floor}"
                        )
                        raise ValueError(msg)
                if require_publish_audit and not (bundle_root / "publish_audit.json").is_file():
                    msg = "Publish gate failed: publish_audit.json missing (requires --publish-signoff)"
                    raise ValueError(msg)
            reach_path = bundle_root / "reachability_report.json"
            if reach_path.is_file():
                reach = json.loads(reach_path.read_text(encoding="utf-8"))
                if int(reach.get("unreachable_answer_gt_count", 0)) > 0:
                    msg = (
                        f"Publish gate failed: {reach['unreachable_answer_gt_count']} "
                        "unreachable answer-GT item(s)"
                    )
                    raise ValueError(msg)


def publish_draft(
    draft_dir: Path,
    *,
    version: str,
    published_root: Path,
    published_by: str = "operator",
    min_items: int = 200,
    skip_gates: bool = False,
    multi_filing_min: int = 0,
    require_publish_audit: bool = False,
    profile_quotas: dict[str, float] | None = None,
    selection_seed: int | None = None,
) -> Path:
    manifest = DatasetManifest.model_validate(
        json.loads((draft_dir / "manifest.json").read_text(encoding="utf-8"))
    )
    report = GenerationReport.model_validate(
        json.loads((draft_dir / "generation_report.json").read_text(encoding="utf-8"))
    )
    config_path = draft_dir / "generation_config.yaml"
    if profile_quotas is None and config_path.is_file():
        config_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        profile_quotas = config_data.get("profile_quotas")
        if selection_seed is None:
            selection_seed = int(config_data.get("random_seed") or 0)

    dest = published_root / f"v{version}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(draft_dir, dest)

    v2 = is_v2_bundle(manifest)
    if v2 and profile_quotas and not skip_gates:
        apply_profile_balanced_dev_split(
            dest,
            profile_quotas=profile_quotas,
            target_count=min_items,
            seed=selection_seed or 0,
        )
        dev_path = dest / "items" / "dev.jsonl"
        dev_items = load_dev_split_items(dev_path)
        manifest = manifest.model_copy(
            update={
                "item_count": len(dev_items),
                "items_hash": items_hash(dev_path),
                "profile_counts": profile_counts(dev_items),
            }
        )

    check_publish_gates(
        manifest,
        report,
        min_items=min_items,
        skip_gates=skip_gates,
        bundle_root=dest,
        multi_filing_min=multi_filing_min,
        require_publish_audit=require_publish_audit,
    )
    published = manifest.model_copy(
        update={
            "version": version,
            "status": DatasetStatus.PUBLISHED,
            "published_at": datetime.now(UTC),
            "published_by": published_by,
            "publish_audit_path": "publish_audit.json"
            if (draft_dir / "publish_audit.json").is_file()
            else None,
        }
    )
    (dest / "manifest.json").write_text(
        json.dumps(published.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    return dest
