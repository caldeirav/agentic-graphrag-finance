"""Paper table export for research reproduction (012)."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from models.evaluation import BenchmarkResult, RankingMetrics
from models.reproduction import (
    AuditRow,
    DeltaRow,
    MetricRow,
    PaperTableExport,
    ProfileMetricRow,
    ReleaseManifest,
)


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


def export_paper_tables(
    summaries: list[VariantRunSummary],
    *,
    release_tag: str,
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


def export_tables_from_disk(
    output_dir: Path,
    *,
    release_tag: str,
    manifest: ReleaseManifest | None = None,
) -> PaperTableExport:
    """Build paper tables from existing per-variant results.json checkpoints."""
    from evaluation.reproduction.manifest import resolve_variant_configs

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
                profiles_by_item={},
                relevance_by_item={},
                ground_truth_by_item={},
            )
        )
    return export_paper_tables(summaries, release_tag=release_tag)
