"""Paper table export for research reproduction (012)."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from models.evaluation import BenchmarkResult, RankingMetrics
from evaluation.judges.outcome_scoring import is_abstention_answer
from evaluation.reproduction.stratum import assign_primary_evidence_source
from models.reproduction import (
    AuditRow,
    DeltaRow,
    MetricRow,
    PaperTableExport,
    ProfileMetricRow,
    ReleaseManifest,
    StratumDeltaRow,
    StratumMetricRow,
)

_STRATA = ("html", "xbrl", "mixed")
_LOW_N_THRESHOLD = 10


@dataclass
class ItemContext:
    inspiration_profile: str
    ground_truth: dict
    relevant_chunk_ids: list[str]


def load_item_contexts(bundle_root: Path, split: str) -> dict[str, ItemContext]:
    """Load per-item profile, ground truth, and relevance labels from the judge bundle."""
    path = bundle_root / "items" / f"{split}.jsonl"
    if not path.is_file():
        msg = f"Custom-judge split not found: {path}"
        raise FileNotFoundError(msg)
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


def item_context_lookup_maps(
    contexts: dict[str, ItemContext],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, dict]]:
    """Split item contexts into the dicts expected by build_variant_summary."""
    profiles = {item_id: ctx.inspiration_profile for item_id, ctx in contexts.items()}
    relevance = {item_id: ctx.relevant_chunk_ids for item_id, ctx in contexts.items()}
    ground_truth = {item_id: ctx.ground_truth for item_id, ctx in contexts.items()}
    return profiles, relevance, ground_truth


@dataclass
class VariantItemRecord:
    item_id: str
    inspiration_profile: str
    result: BenchmarkResult
    has_answer_gt: bool
    has_rubric_gt: bool
    has_relevance_labels: bool


@dataclass
class VariantRunSummary:
    variant_id: str
    records: list[VariantItemRecord] = field(default_factory=list)
    excluded_incomplete: int = 0
    excluded_degraded: int = 0
    excluded_pending_judge: int = 0


def _headline_eligible(record: VariantItemRecord) -> bool:
    status = (record.result.validation_status or "").lower()
    if status in {"incomplete", "non_reproducible"}:
        return False
    if record.result.judge_status == "degraded":
        return False
    if record.result.judge_status == "pending":
        return False
    return True


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ranking_value(metrics: RankingMetrics | None, key: str) -> float | None:
    if metrics is None:
        return None
    return getattr(metrics, key, None)


def build_variant_summary(
    variant_id: str,
    results: list[BenchmarkResult],
    profiles_by_item: dict[str, str],
    relevance_by_item: dict[str, list[str]],
    ground_truth_by_item: dict[str, dict],
) -> VariantRunSummary:
    records: list[VariantItemRecord] = []
    excluded_incomplete = 0
    excluded_degraded = 0
    excluded_pending_judge = 0
    for result in results:
        gt = ground_truth_by_item.get(result.item_id, {})
        record = VariantItemRecord(
            item_id=result.item_id,
            inspiration_profile=profiles_by_item.get(result.item_id, "unknown"),
            result=result,
            has_answer_gt=bool(gt.get("answer")),
            has_rubric_gt=bool(gt.get("rubric")),
            has_relevance_labels=bool(relevance_by_item.get(result.item_id)),
        )
        records.append(record)
        status = (result.validation_status or "").lower()
        if status in {"incomplete", "non_reproducible"}:
            excluded_incomplete += 1
        if result.judge_status == "degraded":
            excluded_degraded += 1
        if result.judge_status == "pending":
            excluded_pending_judge += 1
    return VariantRunSummary(
        variant_id=variant_id,
        records=records,
        excluded_incomplete=excluded_incomplete,
        excluded_degraded=excluded_degraded,
        excluded_pending_judge=excluded_pending_judge,
    )


def _aggregate_metrics(summary: VariantRunSummary) -> dict[str, float | None]:
    eligible = [r for r in summary.records if _headline_eligible(r)]
    out: dict[str, float | None] = {}
    ans = [r.result.outcome_score for r in eligible if r.has_answer_gt]
    rub = [r.result.alignment_score for r in eligible if r.has_rubric_gt]
    fid = [r.result.trajectory_fidelity for r in eligible]
    out["outcome_accuracy"] = _mean(ans) if ans else None
    out["rubric_alignment"] = _mean(rub) if rub else None
    out["trajectory_fidelity"] = _mean(fid) if fid else None

    rank_eligible = [r for r in eligible if r.has_relevance_labels]
    mrr_vals = [
        v
        for r in rank_eligible
        if (v := _ranking_value(r.result.ranking_metrics, "mrr")) is not None
    ]
    map_vals = [
        v
        for r in rank_eligible
        if (v := _ranking_value(r.result.ranking_metrics, "map_score")) is not None
    ]
    ndcg_vals = [
        v
        for r in rank_eligible
        if (v := _ranking_value(r.result.ranking_metrics, "ndcg_at_10")) is not None
    ]
    out["mrr"] = _mean(mrr_vals) if mrr_vals else None
    out["map"] = _mean(map_vals) if map_vals else None
    out["ndcg_at_10"] = _mean(ndcg_vals) if ndcg_vals else None
    return out


def _stratum_for_record(
    record: VariantItemRecord,
    relevance_by_item: dict[str, list[str]],
) -> str:
    chunk_ids = relevance_by_item.get(record.item_id, [])
    return assign_primary_evidence_source(chunk_ids)


def _records_for_stratum(
    summary: VariantRunSummary,
    stratum: str,
    relevance_by_item: dict[str, list[str]],
) -> list[VariantItemRecord]:
    return [
        r
        for r in summary.records
        if _stratum_for_record(r, relevance_by_item) == stratum
    ]


def _abstention_rate(records: list[VariantItemRecord]) -> float:
    eligible = [r for r in records if _headline_eligible(r)]
    if not eligible:
        return 0.0
    abstained = sum(1 for r in eligible if is_abstention_answer(r.result.answer))
    return abstained / len(eligible)


def _append_stratum_exports(
    export: PaperTableExport,
    summaries: list[VariantRunSummary],
    relevance_by_item: dict[str, list[str]],
    metric_names: list[str],
) -> None:
    unknown_items = {
        r.item_id
        for s in summaries
        for r in s.records
        if assign_primary_evidence_source(relevance_by_item.get(r.item_id, [])) == "unknown"
    }
    export.stratum_audit = {"unknown_excluded": len(unknown_items)}

    stratum_summaries: dict[tuple[str, str], VariantRunSummary] = {}
    for summary in summaries:
        for stratum in _STRATA:
            records = _records_for_stratum(summary, stratum, relevance_by_item)
            stratum_summaries[(summary.variant_id, stratum)] = VariantRunSummary(
                variant_id=summary.variant_id,
                records=records,
                excluded_incomplete=summary.excluded_incomplete,
                excluded_degraded=summary.excluded_degraded,
                excluded_pending_judge=summary.excluded_pending_judge,
            )

    agg_by_variant_stratum = {
        key: _aggregate_metrics(sub) for key, sub in stratum_summaries.items()
    }

    for (variant_id, stratum), sub in stratum_summaries.items():
        metrics = agg_by_variant_stratum[(variant_id, stratum)]
        eligible_count = sum(1 for r in sub.records if _headline_eligible(r))
        abstention = _abstention_rate(sub.records)
        for name in metric_names:
            value = metrics.get(name)
            na = ""
            if eligible_count == 0:
                na = "no_eligible_items"
            elif eligible_count < _LOW_N_THRESHOLD:
                na = "low_n"
            export.by_evidence_source_rows.append(
                StratumMetricRow(
                    variant_id=variant_id,
                    primary_evidence_source=stratum,
                    metric_name=name,
                    value=float(value) if value is not None else 0.0,
                    item_count=eligible_count,
                    excluded_incomplete=sub.excluded_incomplete,
                    excluded_degraded=sub.excluded_degraded,
                    abstention_rate=abstention,
                    na_reason=na,
                )
            )
        export.by_evidence_source_rows.append(
            StratumMetricRow(
                variant_id=variant_id,
                primary_evidence_source=stratum,
                metric_name="abstention_rate",
                value=abstention,
                item_count=eligible_count,
                excluded_incomplete=sub.excluded_incomplete,
                excluded_degraded=sub.excluded_degraded,
                abstention_rate=abstention,
                na_reason="low_n" if 0 < eligible_count < _LOW_N_THRESHOLD else "",
            )
        )

    baseline = "graph-full"
    for stratum in _STRATA:
        base_metrics = agg_by_variant_stratum.get((baseline, stratum), {})
        base_count = sum(
            1 for r in stratum_summaries.get((baseline, stratum), VariantRunSummary(variant_id=baseline)).records
            if _headline_eligible(r)
        )
        for summary in summaries:
            if summary.variant_id == baseline:
                continue
            cmp_metrics = agg_by_variant_stratum.get((summary.variant_id, stratum), {})
            cmp_count = sum(
                1
                for r in stratum_summaries.get((summary.variant_id, stratum), VariantRunSummary(variant_id=summary.variant_id)).records
                if _headline_eligible(r)
            )
            low_n = base_count < _LOW_N_THRESHOLD or cmp_count < _LOW_N_THRESHOLD
            for name in metric_names:
                b = base_metrics.get(name)
                c = cmp_metrics.get(name)
                if b is None or c is None:
                    continue
                export.variant_delta_by_source_rows.append(
                    StratumDeltaRow(
                        primary_evidence_source=stratum,
                        baseline_variant=baseline,
                        comparison_variant=summary.variant_id,
                        metric_name=name,
                        delta=float(b) - float(c),
                        baseline_item_count=base_count,
                        comparison_item_count=cmp_count,
                        na_reason="low_n" if low_n else "",
                    )
                )


def export_paper_tables(
    summaries: list[VariantRunSummary],
    *,
    release_tag: str,
    relevance_by_item: dict[str, list[str]] | None = None,
) -> PaperTableExport:
    export = PaperTableExport(release_tag=release_tag)
    metric_names = [
        "outcome_accuracy",
        "rubric_alignment",
        "trajectory_fidelity",
        "mrr",
        "map",
        "ndcg_at_10",
    ]

    agg_by_variant = {s.variant_id: _aggregate_metrics(s) for s in summaries}

    for summary in summaries:
        metrics = agg_by_variant[summary.variant_id]
        eligible_count = sum(1 for r in summary.records if _headline_eligible(r))
        for name in metric_names:
            value = metrics.get(name)
            if value is None:
                export.headline_rows.append(
                    MetricRow(
                        variant_id=summary.variant_id,
                        metric_name=name,
                        value=0.0,
                        item_count=eligible_count,
                        excluded_incomplete=summary.excluded_incomplete,
                        excluded_degraded=summary.excluded_degraded,
                        na_reason="no_eligible_items",
                    )
                )
                continue
            export.headline_rows.append(
                MetricRow(
                    variant_id=summary.variant_id,
                    metric_name=name,
                    value=float(value),
                    item_count=eligible_count,
                    excluded_incomplete=summary.excluded_incomplete,
                    excluded_degraded=summary.excluded_degraded,
                )
            )

        by_profile: dict[str, list[VariantItemRecord]] = defaultdict(list)
        for record in summary.records:
            by_profile[record.inspiration_profile].append(record)

        for profile, records in sorted(by_profile.items()):
            sub = VariantRunSummary(
                variant_id=summary.variant_id,
                records=records,
                excluded_incomplete=summary.excluded_incomplete,
                excluded_degraded=summary.excluded_degraded,
            )
            prof_metrics = _aggregate_metrics(sub)
            for name in metric_names:
                value = prof_metrics.get(name)
                na = ""
                if profile == "finder" and name == "outcome_accuracy":
                    na = "rubric_only"
                    value = None
                export.by_profile_rows.append(
                    ProfileMetricRow(
                        variant_id=summary.variant_id,
                        inspiration_profile=profile,
                        metric_name=name,
                        value=float(value) if value is not None else 0.0,
                        item_count=len(records),
                        na_reason=na,
                    )
                )

        export.audit_rows.append(
            AuditRow(
                variant_id=summary.variant_id,
                excluded_incomplete=summary.excluded_incomplete,
                excluded_degraded=summary.excluded_degraded,
                excluded_pending_judge=summary.excluded_pending_judge,
                included_in_headline=eligible_count,
            )
        )

    baseline = "graph-full"
    for comparison in summaries:
        if comparison.variant_id == baseline:
            continue
        base_metrics = agg_by_variant.get(baseline, {})
        cmp_metrics = agg_by_variant.get(comparison.variant_id, {})
        for name in metric_names:
            b = base_metrics.get(name)
            c = cmp_metrics.get(name)
            if b is None or c is None:
                continue
            export.variant_delta_rows.append(
                DeltaRow(
                    baseline_variant=baseline,
                    comparison_variant=comparison.variant_id,
                    metric_name=name,
                    delta=float(b) - float(c),
                )
            )

    if relevance_by_item:
        _append_stratum_exports(export, summaries, relevance_by_item, metric_names)

    return export


def _write_headline_tex(path: Path, rows: list) -> None:
    variants = sorted({r.variant_id for r in rows})
    metrics = sorted({r.metric_name for r in rows})
    values: dict[tuple[str, str], float] = {}
    for row in rows:
        if row.na_reason:
            continue
        values[(row.variant_id, row.metric_name)] = row.value
    lines = [
        "% auto-generated by agent-query repro export",
        "\\begin{tabular}{l" + "r" * len(metrics) + "}",
        "Variant & " + " & ".join(metrics) + " \\\\",
        "\\hline",
    ]
    for variant in variants:
        cells = [variant]
        for metric in metrics:
            val = values.get((variant, metric))
            cells.append(f"{val:.4f}" if val is not None else "---")
        lines.append(" & ".join(cells) + " \\\\")
    lines.extend(["\\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_paper_tables(export: PaperTableExport, output_dir: Path) -> None:
    tables = output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    if export.stratum_audit:
        manifest_path = output_dir / "export_manifest.json"
        payload: dict = {}
        if manifest_path.is_file():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["stratum_audit"] = export.stratum_audit
        payload["release_tag"] = export.release_tag
        payload["exported_at"] = export.exported_at.isoformat()
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    _write_csv(
        tables / "headline.csv",
        [r.model_dump() for r in export.headline_rows],
        [
            "variant_id",
            "metric_name",
            "value",
            "item_count",
            "excluded_incomplete",
            "excluded_degraded",
            "na_reason",
        ],
    )
    _write_csv(
        tables / "by_profile.csv",
        [r.model_dump() for r in export.by_profile_rows],
        [
            "variant_id",
            "inspiration_profile",
            "metric_name",
            "value",
            "item_count",
            "excluded_incomplete",
            "excluded_degraded",
            "na_reason",
        ],
    )
    _write_csv(
        tables / "variant_delta.csv",
        [r.model_dump() for r in export.variant_delta_rows],
        ["baseline_variant", "comparison_variant", "metric_name", "delta"],
    )
    _write_csv(
        tables / "trajectory_audit.csv",
        [r.model_dump() for r in export.audit_rows],
        [
            "variant_id",
            "excluded_incomplete",
            "excluded_degraded",
            "excluded_pending_judge",
            "included_in_headline",
        ],
    )
    if export.by_evidence_source_rows:
        _write_csv(
            tables / "by_evidence_source.csv",
            [r.model_dump() for r in export.by_evidence_source_rows],
            [
                "variant_id",
                "primary_evidence_source",
                "metric_name",
                "value",
                "item_count",
                "abstention_rate",
                "excluded_incomplete",
                "excluded_degraded",
                "na_reason",
            ],
        )
    if export.variant_delta_by_source_rows:
        _write_csv(
            tables / "variant_delta_by_source.csv",
            [r.model_dump() for r in export.variant_delta_by_source_rows],
            [
                "primary_evidence_source",
                "baseline_variant",
                "comparison_variant",
                "metric_name",
                "delta",
                "baseline_item_count",
                "comparison_item_count",
                "na_reason",
            ],
        )


def export_tables_from_disk(
    output_dir: Path,
    *,
    release_tag: str,
    manifest: ReleaseManifest | None = None,
    repo_root: Path | None = None,
) -> PaperTableExport:
    """Build paper tables from existing per-variant results.json checkpoints."""
    from evaluation.reproduction.manifest import resolve_variant_configs

    profiles_by_item: dict[str, str] = {}
    relevance_by_item: dict[str, list[str]] = {}
    ground_truth_by_item: dict[str, dict] = {}
    if manifest is not None:
        root = repo_root or Path.cwd()
        bundle_root = root / manifest.custom_judge_bundle_path
        contexts = load_item_contexts(bundle_root, manifest.eval_split)
        profiles_by_item, relevance_by_item, ground_truth_by_item = item_context_lookup_maps(
            contexts
        )

    summaries: list[VariantRunSummary] = []
    variant_ids: list[str] = []
    if manifest is not None:
        variant_ids = [v.variant_id for v in resolve_variant_configs(manifest)]
    else:
        variant_ids = sorted(
            p.name for p in output_dir.iterdir() if p.is_dir() and (p / "results.json").is_file()
        )

    for variant_id in variant_ids:
        results_path = output_dir / variant_id / "results.json"
        if not results_path.is_file():
            continue
        rows = json.loads(results_path.read_text(encoding="utf-8"))
        results = [BenchmarkResult.model_validate(row) for row in rows]
        summaries.append(
            build_variant_summary(
                variant_id,
                results,
                profiles_by_item,
                relevance_by_item,
                ground_truth_by_item,
            )
        )
    return export_paper_tables(
        summaries,
        release_tag=release_tag,
        relevance_by_item=relevance_by_item,
    )
