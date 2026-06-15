"""HTML and copy renderers for reproduction reports (014)."""

from __future__ import annotations

import html
import os
from datetime import datetime
from pathlib import Path

from evaluation.reproduction.report_formatters import (
    build_booktabs_latex,
    format_display_number,
    is_numeric_column,
    pivot_headline_table,
    rows_to_csv,
    rows_to_markdown,
    table_provenance,
)
from evaluation.reproduction.report_loader import bundle_source_hashes, is_v2_repro_bundle
from evaluation.reproduction.report_models import (
    AUDIT_COLUMN_LABELS,
    METRIC_CATALOG,
    PRIMARY_METRICS,
    SMOKE_ITEM_THRESHOLD,
    STANDARD_VARIANTS,
    AggregatedInvestigationNote,
    ItemResultRecord,
    PaperTableId,
    PaperTableView,
    ReportArtifact,
    ReproOutputBundle,
    RunAnomaly,
    RunSummaryView,
    VariantComparisonView,
    VariantCount,
    VariantMetricSeries,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = REPO_ROOT / "templates" / "reproduction_report.html"
DEFAULT_DELTA_THRESHOLD = 0.10
MAX_INVESTIGATION_NOTES = 25
HIGHLIGHT_STATUSES = frozenset({"degraded", "pending", "not_evaluable"})
_EXPECTED_ZERO_CITATION_VARIANTS = frozenset({"ablation-no-walker", "ablation-xbrl-only"})
_HTML_HIDDEN_PAPER_TABLES = frozenset(
    {
        PaperTableId.BY_PROFILE,
        PaperTableId.VARIANT_DELTA,
        PaperTableId.VARIANT_DELTA_BY_SOURCE,
    }
)


def build_paper_table_views(bundle: ReproOutputBundle) -> list[PaperTableView]:
    release_tag = bundle.repro_run.release_tag
    v2 = is_v2_repro_bundle(bundle)
    views: list[PaperTableView] = []
    for table_id in PaperTableId:
        data = bundle.tables.get(table_id.value)
        if data is None:
            continue
        rows = data.rows
        if v2 and table_id in (PaperTableId.HEADLINE, PaperTableId.BY_PROFILE, PaperTableId.BY_EVIDENCE_SOURCE):
            rows = [r for r in rows if r.get("metric_name") != "rubric_alignment"]
        prov = table_provenance(table_id, rows, release_tag)
        views.append(
            PaperTableView(
                table_id=table_id,
                columns=data.columns,
                rows=rows,
                latex_copy=build_booktabs_latex(
                    table_id, data.columns, rows, release_tag=release_tag, provenance=prov
                ),
                csv_copy=rows_to_csv(data.columns, rows),
                markdown_copy=rows_to_markdown(data.columns, rows),
                provenance=prov,
            )
        )
    return views


def build_run_summary(bundle: ReproOutputBundle) -> RunSummaryView:
    repro = bundle.repro_run
    duration: float | None = None
    if repro.completed_at and repro.started_at:
        duration = (repro.completed_at - repro.started_at).total_seconds()

    audit_table = bundle.tables.get("trajectory_audit")
    audit_by_variant = (
        {row["variant_id"]: row for row in audit_table.rows} if audit_table else {}
    )

    variant_counts: list[VariantCount] = []
    seen: set[str] = set()
    deduped_runs: dict[str, object] = {}
    for vr in repro.variant_runs:
        prev = deduped_runs.get(vr.variant_id)
        if prev is None or (vr.mlflow_parent_run_id and not prev.mlflow_parent_run_id):
            deduped_runs[vr.variant_id] = vr

    if len(deduped_runs) < len({vr.variant_id for vr in repro.variant_runs}):
        pass  # flagged in detect_run_anomalies

    for vr in deduped_runs.values():
        seen.add(vr.variant_id)
        audit = audit_by_variant.get(vr.variant_id, {})
        items_total = int(audit.get("included_in_headline", "0") or 0) + int(
            audit.get("excluded_incomplete", "0") or 0
        ) + int(audit.get("excluded_degraded", "0") or 0) + int(
            audit.get("excluded_pending_judge", "0") or 0
        )
        if items_total == 0 and vr.variant_id in bundle.variant_results:
            items_total = len(bundle.variant_results[vr.variant_id])
        variant_counts.append(
            VariantCount(
                variant_id=vr.variant_id,
                items_total=items_total,
                excluded_incomplete=int(
                    audit.get("excluded_incomplete", vr.items_excluded_incomplete) or 0
                ),
                excluded_degraded=int(
                    audit.get("excluded_degraded", vr.items_excluded_degraded) or 0
                ),
                excluded_pending_judge=int(audit.get("excluded_pending_judge", "0") or 0),
                has_results=vr.variant_id not in bundle.incomplete_variants,
            )
        )

    for variant_id in bundle.incomplete_variants:
        if variant_id in seen:
            continue
        variant_counts.append(
            VariantCount(variant_id=variant_id, items_total=0, has_results=False)
        )

    mlflow_links: list[str] = []
    tracking = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    for vr in deduped_runs.values():
        if not vr.mlflow_parent_run_id:
            continue
        if tracking and not tracking.startswith("$"):
            mlflow_links.append(f"{tracking.rstrip('/')}/#/experiments/0/runs/{vr.mlflow_parent_run_id}")
        else:
            mlflow_links.append(f"mlflow-run:{vr.mlflow_parent_run_id} ({vr.variant_id})")

    export_summary = None
    if bundle.export_manifest:
        export_summary = {
            k: bundle.export_manifest[k]
            for k in ("release_tag", "exported_at", "variant_ids")
            if k in bundle.export_manifest
        }
        if not export_summary:
            export_summary = dict(bundle.export_manifest)

    return RunSummaryView(
        release_tag=repro.release_tag,
        repro_run_id=repro.repro_run_id,
        started_at=repro.started_at,
        completed_at=repro.completed_at,
        duration_seconds=duration,
        defer_judge=repro.defer_judge,
        resume_mode=bool(repro.completed_variants),
        variant_counts=variant_counts,
        mlflow_links=mlflow_links,
        export_manifest_summary=export_summary,
        manifest_unavailable=bundle.release_manifest is None,
    )


def build_variant_comparison(bundle: ReproOutputBundle) -> VariantComparisonView:
    headline = bundle.tables.get("headline")
    if headline is None:
        return VariantComparisonView(metric_names=list(PRIMARY_METRICS), series=[])

    by_variant: dict[str, dict[str, float]] = {}
    for row in headline.rows:
        vid = row["variant_id"]
        metric = row["metric_name"]
        if metric not in PRIMARY_METRICS:
            continue
        by_variant.setdefault(vid, {})[metric] = float(row["value"])

    baseline = by_variant.get("graph-full", {})
    series: list[VariantMetricSeries] = []
    order = [v for v in STANDARD_VARIANTS if v in by_variant]
    order.extend(sorted(v for v in by_variant if v not in order))

    for vid in order:
        values = by_variant[vid]
        deltas = {
            m: values.get(m, 0.0) - baseline.get(m, 0.0) for m in PRIMARY_METRICS if m in values
        }
        series.append(
            VariantMetricSeries(
                variant_id=vid,
                values_by_metric=values,
                delta_vs_baseline=deltas,
            )
        )

    return VariantComparisonView(
        metric_names=list(PRIMARY_METRICS),
        series=series,
        baseline_variant="graph-full",
    )


def _binding_miss(record: ItemResultRecord) -> bool:
    status = (record.validation_status or "").lower()
    if "binding" in status:
        return True
    if record.citation_count == 0 and record.judge_status == "ok":
        return True
    return False


def _metric_delta(a: ItemResultRecord, b: ItemResultRecord, metric: str) -> float | None:
    av = getattr(a, metric, None)
    bv = getattr(b, metric, None)
    if av is None or bv is None:
        return None
    return abs(float(av) - float(bv))


def compute_investigation_flags(
    bundle: ReproOutputBundle,
    *,
    delta_threshold: float = DEFAULT_DELTA_THRESHOLD,
) -> None:
    """Mutates item records in bundle with FR-014 flags."""
    baseline_items = {r.item_id: r for r in bundle.variant_results.get("graph-full", [])}
    for variant_id, records in bundle.variant_results.items():
        for record in records:
            flags = set(record.flags)
            if _binding_miss(record):
                flags.add("binding_miss")
            if variant_id != "graph-full":
                base = baseline_items.get(record.item_id)
                if base is not None:
                    for metric in PRIMARY_METRICS:
                        delta = _metric_delta(record, base, metric)
                        if delta is not None and delta >= delta_threshold:
                            flags.add("high_delta")
                            break
            record.flags = sorted(flags)


def render_latex_only(
    bundle: ReproOutputBundle,
    table_ids: list[PaperTableId] | None = None,
) -> str:
    selected = table_ids or list(PaperTableId)
    views = build_paper_table_views(bundle)
    by_id = {v.table_id: v for v in views}
    chunks: list[str] = []
    for tid in selected:
        view = by_id.get(tid)
        if view is not None:
            chunks.append(view.latex_copy)
    return "\n".join(chunks)


def _render_warnings_html(warnings: list[str]) -> str:
    if not warnings:
        return ""
    items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
    return f'<section class="warnings"><strong>Warnings</strong><ul>{items}</ul></section>'


def _render_summary_html(summary: RunSummaryView) -> str:
    duration = ""
    if summary.duration_seconds is not None:
        mins = int(summary.duration_seconds // 60)
        secs = int(summary.duration_seconds % 60)
        duration = f"{mins}m {secs}s"

    flags = []
    if summary.defer_judge:
        flags.append("defer-judge")
    if summary.resume_mode:
        flags.append("resume")

    cards = [
        ("Release", summary.release_tag),
        ("Run ID", summary.repro_run_id[:8] + "…"),
        ("Duration", duration or "—"),
        ("Mode", ", ".join(flags) if flags else "standard"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div></div>'
        for label, value in cards
    )

    variant_rows = ""
    for vc in summary.variant_counts:
        status = "complete" if vc.has_results else "incomplete"
        variant_rows += (
            f"<tr><td>{html.escape(vc.variant_id)}</td>"
            f"<td>{vc.items_total}</td>"
            f"<td>{vc.excluded_incomplete}</td>"
            f"<td>{vc.excluded_degraded}</td>"
            f"<td>{vc.excluded_pending_judge}</td>"
            f"<td>{status}</td></tr>"
        )

    mlflow_html = ""
    if summary.mlflow_links:
        links = "".join(
            f'<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(u)}</a></li>'
            if u.startswith("http")
            else f"<li>{html.escape(u)}</li>"
            for u in summary.mlflow_links
        )
        mlflow_html = f"<h3>MLflow references</h3><ul>{links}</ul>"

    manifest_note = ""
    if summary.manifest_unavailable:
        manifest_note = "<p><em>Release manifest unavailable; provenance from on-disk artifacts only.</em></p>"

    return f"""<section id="summary">
<h2>Run Summary</h2>
{manifest_note}
<div class="summary-grid">{cards_html}</div>
<h3>Variant counts</h3>
<table><thead><tr>
<th>Variant</th><th>Items</th><th>Excluded incomplete</th>
<th>Excluded degraded</th><th>Pending judge</th><th>Status</th>
</tr></thead><tbody>{variant_rows}</tbody></table>
{mlflow_html}
</section>"""


def _render_export_manifest_html(summary: RunSummaryView) -> str:
    if not summary.export_manifest_summary:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in summary.export_manifest_summary.items()
    )
    return f"""<section id="export-manifest"><h2>Export manifest</h2>
<table><tbody>{rows}</tbody></table></section>"""


def _render_headline_tex_html(bundle: ReproOutputBundle, generated_latex: str) -> str:
    if not bundle.headline_tex:
        return ""
    return f"""<section id="headline-tex"><h2>Headline TeX (on disk)</h2>
<p><em>Compare exported <code>headline.tex</code> with generated LaTeX copy below.</em></p>
<pre class="headline-tex">{html.escape(bundle.headline_tex)}</pre>
<h3>Generated LaTeX (headline)</h3>
<pre class="headline-tex">{html.escape(generated_latex[:4000])}</pre>
</section>"""


def _column_header(col: str) -> tuple[str, str]:
    if col in METRIC_CATALOG:
        md = METRIC_CATALOG[col]
        return md.display_name, md.definition
    if col in AUDIT_COLUMN_LABELS:
        return AUDIT_COLUMN_LABELS[col]
    label = col.replace("_", " ").title()
    return label, label


def _cap_investigation_notes(
    notes: list[AggregatedInvestigationNote],
) -> list[AggregatedInvestigationNote]:
    if len(notes) <= MAX_INVESTIGATION_NOTES:
        return notes
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(notes, key=lambda n: (severity_rank.get(n.severity, 9), -n.item_count))[
        :MAX_INVESTIGATION_NOTES
    ]


def aggregate_investigation_notes(bundle: ReproOutputBundle) -> list[AggregatedInvestigationNote]:
    """Group per-item patterns into bounded operator summaries (FR-008–FR-011)."""
    notes: list[AggregatedInvestigationNote] = []
    repro = bundle.repro_run
    headline = bundle.tables.get("headline")

    variant_ids = [vr.variant_id for vr in repro.variant_runs]
    if len(variant_ids) != len(set(variant_ids)):
        notes.append(
            AggregatedInvestigationNote(
                severity="warning",
                pattern_code="DUPLICATE_VARIANT_RUNS",
                message="repro_run.json lists duplicate variant_runs entries",
                item_count=0,
                hint="Summary deduplicates by variant_id; consider cleaning repro_run.json on next export.",
                expandable=False,
            )
        )

    if headline and headline.rows:
        n = int(headline.rows[0].get("item_count", "0") or 0)
        if n <= SMOKE_ITEM_THRESHOLD:
            notes.append(
                AggregatedInvestigationNote(
                    severity="info",
                    pattern_code="SMALL_SAMPLE",
                    message=f"Small benchmark sample (n={n} items per variant)",
                    item_count=n,
                    hint="paper-live-smoke uses --max-items 2; treat ranking splits as indicative only.",
                    expandable=False,
                )
            )

        rubric_vals = [
            float(r["value"]) for r in headline.rows if r["metric_name"] == "rubric_alignment"
        ]
        if rubric_vals and all(v == 0.0 for v in rubric_vals) and not is_v2_repro_bundle(bundle):
            notes.append(
                AggregatedInvestigationNote(
                    severity="warning",
                    pattern_code="RUBRIC_ALIGNMENT_ZERO",
                    message="Rubric alignment is 0.0 for every variant",
                    item_count=len(rubric_vals),
                    hint="Check judge populates claim_presence; items may lack rubric GT.",
                    expandable=False,
                )
            )

    struct_zero = all(
        vr.structural_metrics.accession_binding_accuracy == 0.0
        and vr.structural_metrics.section_path_hit_rate == 0.0
        for vr in repro.variant_runs
    )
    if struct_zero and repro.variant_runs:
        notes.append(
            AggregatedInvestigationNote(
                severity="warning",
                pattern_code="STRUCTURAL_METRICS_ZERO",
                message="Structural binding metrics are 0.0 for all variant runs",
                item_count=len(repro.variant_runs),
                hint="Inspect structural_metrics wiring or expected_bindings in benchmark items.",
                expandable=False,
            )
        )

    zero_cite_buckets: dict[str, list[str]] = {}
    high_outcome_zero_ndcg: dict[str, list[str]] = {}

    for variant_id, records in bundle.variant_results.items():
        for rec in records:
            if rec.judge_status == "ok" and rec.citation_count == 0 and variant_id != "flat-chunk":
                zero_cite_buckets.setdefault(variant_id, []).append(rec.item_id)
            if (
                rec.outcome_score is not None
                and rec.outcome_score >= 0.9
                and rec.ndcg_at_10 is not None
                and rec.ndcg_at_10 == 0.0
                and variant_id not in _EXPECTED_ZERO_CITATION_VARIANTS
            ):
                high_outcome_zero_ndcg.setdefault(variant_id, []).append(rec.item_id)

    for variant_id, item_ids in zero_cite_buckets.items():
        if variant_id in _EXPECTED_ZERO_CITATION_VARIANTS:
            notes.append(
                AggregatedInvestigationNote(
                    severity="info",
                    pattern_code="ABLATION_ZERO_CITATIONS",
                    variant_id=variant_id,
                    message=(
                        f"{variant_id}: {len(item_ids)} items with judge ok but zero citations "
                        "(expected ablation pattern)"
                    ),
                    item_count=len(item_ids),
                    example_item_ids=item_ids[:5],
                    hint="No-walker/xbrl-only cannot reach HTML narrative relevance labels.",
                )
            )
        else:
            notes.append(
                AggregatedInvestigationNote(
                    severity="warning",
                    pattern_code="JUDGE_OK_ZERO_CITATIONS",
                    variant_id=variant_id,
                    message=f"{variant_id}: {len(item_ids)} items with judge ok but zero citations",
                    item_count=len(item_ids),
                    example_item_ids=item_ids[:5],
                    hint="Answer may be ungrounded; open item drill-down and results.json.",
                )
            )

    for variant_id, item_ids in high_outcome_zero_ndcg.items():
        notes.append(
            AggregatedInvestigationNote(
                severity="warning",
                pattern_code="HIGH_OUTCOME_ZERO_NDCG",
                variant_id=variant_id,
                message=(
                    f"{variant_id}: {len(item_ids)} items with high outcome but nDCG@10=0"
                ),
                item_count=len(item_ids),
                example_item_ids=item_ids[:5],
                hint="Judge score and retrieval ranking disagree; inspect citations vs relevance labels.",
            )
        )

    if headline:
        by_var: dict[str, dict[str, float]] = {}
        for row in headline.rows:
            by_var.setdefault(row["variant_id"], {})[row["metric_name"]] = float(row["value"])

        for vid, metrics in by_var.items():
            mrr = metrics.get("mrr")
            if mrr is not None and mrr <= 0.0:
                records = bundle.variant_results.get(vid, [])
                total_cites = sum(r.citation_count for r in records)
                if vid == "flat-chunk" and total_cites > 0:
                    notes.append(
                        AggregatedInvestigationNote(
                            severity="info",
                            pattern_code="FLAT_CHUNK_ZERO_RANKING",
                            variant_id=vid,
                            message=f"{vid}: MRR/MAP/nDCG are 0 despite {total_cites} total citations",
                            item_count=len(records),
                            hint="Citations may not overlap graph-grounded relevance labels.",
                            expandable=False,
                        )
                    )
                elif vid in _EXPECTED_ZERO_CITATION_VARIANTS:
                    notes.append(
                        AggregatedInvestigationNote(
                            severity="info",
                            pattern_code="ABLATION_ZERO_RANKING",
                            variant_id=vid,
                            message=f"{vid}: MRR/MAP/nDCG are 0 (expected for this ablation)",
                            item_count=len(records),
                            hint="Ablation cannot retrieve HTML-labeled narrative chunks.",
                            expandable=False,
                        )
                    )

        gf = by_var.get("graph-full", {})
        for vid, metrics in by_var.items():
            if vid == "graph-full":
                continue
            oa = metrics.get("outcome_accuracy")
            gf_oa = gf.get("outcome_accuracy")
            if oa is None or gf_oa is None or oa <= gf_oa + 0.05:
                continue
            cmp_records = bundle.variant_results.get(vid, [])
            cmp_cites = sum(r.citation_count for r in cmp_records)
            cmp_mrr = metrics.get("mrr", 0.0) or 0.0
            if cmp_cites == 0 and cmp_mrr <= 0.0:
                continue
            notes.append(
                AggregatedInvestigationNote(
                    severity="info",
                    pattern_code="OUTCOME_EXCEEDS_BASELINE",
                    variant_id=vid,
                    message=f"{vid} outcome_accuracy ({oa:.2f}) exceeds graph-full ({gf_oa:.2f})",
                    item_count=1,
                    hint="Verify item-level results before citing in paper.",
                    expandable=False,
                )
            )

        gf_oa = gf.get("outcome_accuracy")
        fc_oa = by_var.get("flat-chunk", {}).get("outcome_accuracy")
        html_gf: float | None = None
        html_fc: float | None = None
        stratum_table = bundle.tables.get("by_evidence_source")
        if stratum_table:
            for row in stratum_table.rows:
                if row.get("primary_evidence_source") != "html":
                    continue
                if row.get("metric_name") != "outcome_accuracy":
                    continue
                if row.get("variant_id") == "graph-full":
                    html_gf = float(row["value"])
                if row.get("variant_id") == "flat-chunk":
                    html_fc = float(row["value"])
        regression = False
        if gf_oa is not None and fc_oa is not None and gf_oa <= fc_oa:
            regression = True
        if html_gf is not None and html_fc is not None and html_gf <= html_fc:
            regression = True
        if regression:
            example_ids: list[str] = []
            gf_records = bundle.variant_results.get("graph-full", [])
            fc_records = bundle.variant_results.get("flat-chunk", [])
            for g_rec, f_rec in zip(gf_records[:5], fc_records[:5], strict=False):
                if (
                    f_rec.outcome_score is not None
                    and g_rec.outcome_score is not None
                    and f_rec.outcome_score > g_rec.outcome_score
                ):
                    example_ids.append(g_rec.item_id)
            pooled_msg = ""
            if gf_oa is not None and fc_oa is not None:
                pooled_msg = (
                    f"graph-full outcome_accuracy ({gf_oa:.2f}) does not exceed "
                    f"flat-chunk ({fc_oa:.2f}) on pooled headline"
                )
            html_msg = ""
            if html_gf is not None and html_fc is not None and html_gf <= html_fc:
                html_msg = f"HTML stratum gf={html_gf:.2f} fc={html_fc:.2f}"
            message = "; ".join(part for part in (pooled_msg, html_msg) if part) or (
                "SC-001 outcome ordering regression detected"
            )
            notes.append(
                AggregatedInvestigationNote(
                    severity="warning",
                    pattern_code="OUTCOME_ORDERING_REGRESSION",
                    message=message,
                    item_count=max(1, len(example_ids)),
                    example_item_ids=example_ids[:5],
                    hint="SC-001 target not met; review v3 re-score and bundle v1.1.0 before citing.",
                    expandable=bool(example_ids),
                )
            )

    incomplete_va = 0
    for records in bundle.variant_results.values():
        for rec in records:
            if rec.judge_status != "ok":
                continue
            scores = rec.rubric_scores or {}
            if scores and "value_alignment" not in scores and rec.outcome_score is not None:
                incomplete_va += 1
    if incomplete_va:
        notes.append(
            AggregatedInvestigationNote(
                severity="warning",
                pattern_code="INCOMPLETE_JUDGE_CRITERIA",
                message=f"{incomplete_va} judged items lack value_alignment in stored verdicts",
                item_count=incomplete_va,
                hint="Re-run judge-batch with v3; missing VA counts as zero in outcome_accuracy.",
                expandable=False,
            )
        )

    return _cap_investigation_notes(notes)


def detect_run_anomalies(bundle: ReproOutputBundle) -> list[RunAnomaly]:
    """Backward-compatible wrapper over aggregated investigation notes."""
    return [
        RunAnomaly(severity=n.severity, message=n.message, hint=n.hint)
        for n in aggregate_investigation_notes(bundle)
    ]


def _render_aggregated_notes_html(notes: list[AggregatedInvestigationNote]) -> str:
    if not notes:
        return (
            '<section id="anomalies"><h2>Investigation notes</h2>'
            "<p>No automated anomalies flagged for this output.</p></section>"
        )
    items: list[str] = []
    for note in notes:
        hint = f"<br/><small>{html.escape(note.hint)}</small>" if note.hint else ""
        examples = ""
        if note.expandable and note.example_item_ids:
            links = ", ".join(
                f'<a href="#item-{html.escape(iid)}">{html.escape(iid)}</a>'
                for iid in note.example_item_ids
            )
            examples = f"<details><summary>Examples ({len(note.example_item_ids)})</summary><p>{links}</p></details>"
        items.append(
            f"<li class='anomaly-{note.severity}'><strong>[{note.severity}]</strong> "
            f"{html.escape(note.message)}{hint}{examples}</li>"
        )
    return (
        '<section id="anomalies"><h2>Investigation notes</h2>'
        f"<p>{len(notes)} aggregated checks (max {MAX_INVESTIGATION_NOTES}).</p>"
        f"<ul class='anomaly-list'>{''.join(items)}</ul></section>"
    )


def _render_anomalies_html(anomalies: list[RunAnomaly]) -> str:
    if not anomalies:
        return (
            '<section id="anomalies"><h2>Investigation notes</h2>'
            "<p>No automated anomalies flagged for this output.</p></section>"
        )
    items: list[str] = []
    for a in anomalies:
        hint = f"<br/><small>{html.escape(a.hint)}</small>" if a.hint else ""
        items.append(
            f"<li class='anomaly-{a.severity}'><strong>[{a.severity}]</strong> "
            f"{html.escape(a.message)}{hint}</li>"
        )
    return (
        '<section id="anomalies"><h2>Investigation notes</h2>'
        "<p>Automated checks on this repro output; confirm in item drill-down before acting.</p>"
        f"<ul class='anomaly-list'>{''.join(items)}</ul></section>"
    )


def _render_evidence_source_matrix_html(bundle: ReproOutputBundle) -> str:
    """Pivot by_evidence_source: variant × stratum rows, metric columns."""
    table = bundle.tables.get("by_evidence_source")
    if table is None or not table.rows:
        return ""
    active_rows = [r for r in table.rows if not r.get("na_reason")]
    if not active_rows:
        return ""
    metric_names = sorted({r["metric_name"] for r in active_rows})
    pivot: dict[tuple[str, str], dict[str, str]] = {}
    for row in active_rows:
        key = (row["variant_id"], row["primary_evidence_source"])
        bucket = pivot.setdefault(key, {})
        bucket[row["metric_name"]] = row.get("value", "")
        if row.get("item_count"):
            bucket["item_count"] = row["item_count"]
    columns = ["variant_id", "primary_evidence_source", "item_count", *metric_names]
    matrix_rows = [
        {
            "variant_id": key[0],
            "primary_evidence_source": key[1],
            **values,
        }
        for key, values in sorted(pivot.items())
    ]
    matrix = _render_score_matrix_html(columns, matrix_rows, table_class="score-table outcome-table")
    return (
        '<section id="evidence-source"><h2>By evidence source</h2>'
        "<p>Primary evidence stratum per variant; one row per "
        "<code>variant_id</code> × <code>primary_evidence_source</code> "
        "with all exported metrics as columns.</p>"
        f'<div class="score-table-wrap">{matrix}</div></section>'
    )


def _render_outcome_by_profile_html(bundle: ReproOutputBundle) -> str:
    return ""


def _render_outcome_by_stratum_html(bundle: ReproOutputBundle) -> str:
    return _render_evidence_source_matrix_html(bundle)


def _render_stratified_html(bundle: ReproOutputBundle) -> str:
    return ""


def _render_metric_glossary_html(columns: list[str]) -> str:
    metric_cols = [c for c in columns if c in METRIC_CATALOG]
    if not metric_cols:
        return ""
    rows = []
    for col in metric_cols:
        md = METRIC_CATALOG[col]
        rows.append(
            f"<tr><td><code>{html.escape(md.metric_id)}</code></td>"
            f"<td>{html.escape(md.display_name)}</td>"
            f"<td>{html.escape(md.definition)}</td>"
            f"<td>{html.escape(md.source)}</td></tr>"
        )
    return (
        '<details id="metric-glossary" class="metric-glossary" open>'
        "<summary>Metric definitions</summary>"
        "<table><thead><tr><th>ID</th><th>Name</th><th>Definition</th><th>Source</th>"
        "</tr></thead><tbody>"
        f"{''.join(rows)}</tbody></table></details>"
    )


def _render_score_matrix_html(
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    baseline_variant: str = "graph-full",
    table_class: str = "score-table",
) -> str:
    parts = [f"<table class='{table_class}'><thead><tr>"]
    for col in columns:
        display, tooltip = _column_header(col)
        cls = "num" if is_numeric_column(col) else "label"
        parts.append(
            f"<th class='{cls}' title=\"{html.escape(tooltip)}\">{html.escape(display)}</th>"
        )
    parts.append("</tr></thead><tbody>")
    for row in rows:
        is_baseline = row.get("variant_id") == baseline_variant
        tr_cls = "baseline-row" if is_baseline else ""
        parts.append(f"<tr class='{tr_cls}'>")
        for col in columns:
            raw = row.get(col, "")
            cls = "num" if is_numeric_column(col) else "label"
            if col == "variant_id":
                text = html.escape(str(raw))
            else:
                text = html.escape(format_display_number(str(raw)))
            parts.append(f"<td class='{cls}'>{text}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _render_comparison_html(comparison: VariantComparisonView, bundle: ReproOutputBundle) -> str:
    headline = bundle.tables.get("headline")
    if headline is None or not headline.rows:
        return ""

    primary_rows = [r for r in headline.rows if r.get("metric_name") in PRIMARY_METRICS]
    columns, rows = pivot_headline_table(primary_rows)
    task_n = next(
        (r.get("item_count", "") for r in primary_rows if r.get("metric_name") == "task_success"),
        "",
    )
    v2_note = (
        " Value-alignment only (paper-v2.0); missing VA counts as 0."
        if is_v2_repro_bundle(bundle)
        else ""
    )
    n_note = (
        f" <code>task_success</code> aggregates all eligible items (n={html.escape(task_n)})."
        f"{v2_note}"
        if task_n
        else ""
    )
    matrix = _render_score_matrix_html(
        columns,
        rows,
        baseline_variant=comparison.baseline_variant,
    )
    return (
        '<section id="comparison"><h2>Variant comparison</h2>'
        "<p>Variants as rows, primary evaluation metrics as columns "
        f"(baseline: <code>{html.escape(comparison.baseline_variant)}</code>). "
        f"{n_note} "
        "Hover column headers for definitions.</p>"
        f'<div class="score-table-wrap">{matrix}</div>'
        f"{_render_metric_glossary_html(columns)}</section>"
    )


def _render_tables_html(views: list[PaperTableView], bundle: ReproOutputBundle) -> str:
    visible = [v for v in views if v.table_id not in _HTML_HIDDEN_PAPER_TABLES]
    parts = ['<section id="paper-tables"><h2>Paper tables</h2>']
    for view in visible:
        tid = view.table_id.value
        parts.append(f"<h3>{html.escape(tid.replace('_', ' ').title())}</h3>")
        parts.append(
            f"<div class='copy-row'>"
            f"<button type='button' onclick=\"copyText('latex-{tid}', this)\">Copy LaTeX</button>"
            f"<button type='button' onclick=\"copyText('csv-{tid}', this)\">Copy CSV</button>"
            f"<button type='button' onclick=\"copyText('md-{tid}', this)\">Copy Markdown</button>"
            f"</div>"
        )
        parts.append(f"<pre id='latex-{tid}' class='hidden'>{html.escape(view.latex_copy)}</pre>")
        parts.append(f"<pre id='csv-{tid}' class='hidden'>{html.escape(view.csv_copy)}</pre>")
        parts.append(f"<pre id='md-{tid}' class='hidden'>{html.escape(view.markdown_copy)}</pre>")

        if view.table_id == PaperTableId.HEADLINE:
            columns, rows = pivot_headline_table(view.rows)
            parts.append(
                "<p><em>Comparison layout below; copy buttons use canonical long-format export.</em></p>"
            )
            parts.append(_render_score_matrix_html(columns, rows))
            continue

        parts.append("<table><thead><tr>")
        parts.append("".join(f"<th>{html.escape(c)}</th>" for c in view.columns))
        parts.append("</tr></thead><tbody>")
        for row in view.rows:
            parts.append("<tr>")
            for col in view.columns:
                parts.append(f"<td>{html.escape(format_display_number(row.get(col, '')))}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
    parts.append("</section>")
    return "".join(parts)


def _status_class(status: str) -> str:
    safe = status.replace("-", "_")
    if safe in HIGHLIGHT_STATUSES or status in HIGHLIGHT_STATUSES:
        return f"status-{safe}"
    return ""


def _variant_display_order(bundle: ReproOutputBundle) -> list[str]:
    keys = set(bundle.variant_results.keys())
    order = [v for v in STANDARD_VARIANTS if v in keys]
    order.extend(sorted(k for k in keys if k not in order))
    return order


def _item_records_by_id(bundle: ReproOutputBundle) -> dict[str, dict[str, ItemResultRecord]]:
    by_item: dict[str, dict[str, ItemResultRecord]] = {}
    for variant_id, records in bundle.variant_results.items():
        for record in records:
            by_item.setdefault(record.item_id, {})[variant_id] = record
    return by_item


def _format_score(value: float | None, *, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _render_rubric_scores_html(scores: dict[str, float]) -> str:
    if not scores:
        return "<em>No judge scores recorded</em>"
    parts = [
        f"<li><code>{html.escape(k)}</code>: {_format_score(v)}</li>"
        for k, v in sorted(scores.items())
    ]
    return f"<ul class='score-list'>{''.join(parts)}</ul>"


def _render_variant_detail_panel(record: ItemResultRecord | None, variant_id: str) -> str:
    if record is None:
        return (
            f"<div class='variant-panel missing' data-variant='{html.escape(variant_id)}'>"
            f"<h4>{html.escape(variant_id)}</h4><p><em>No result for this variant</em></p></div>"
        )
    flags_txt = ", ".join(record.flags) if record.flags else "—"
    ranking = (
        f"MRR {_format_score(record.mrr)}, MAP {_format_score(record.map_score)}, "
        f"nDCG@10 {_format_score(record.ndcg_at_10)}"
    )
    structural = ""
    if record.structural_metrics:
        sm = ", ".join(
            f"{html.escape(k)}={_format_score(v)}" for k, v in sorted(record.structural_metrics.items())
        )
        structural = f"<p><strong>Structural metrics:</strong> {sm}</p>"
    failure = ""
    if record.failure_reason:
        failure = f"<p><strong>Failure:</strong> {html.escape(record.failure_reason)}</p>"
    answer_body = record.answer_text or record.answer_excerpt or "—"
    return (
        f"<div class='variant-panel {_status_class(record.judge_status)}' "
        f"data-variant='{html.escape(variant_id)}'>"
        f"<h4>{html.escape(variant_id)}</h4>"
        f"<p><strong>Judge:</strong> {html.escape(record.judge_status or '—')} · "
        f"<strong>Validation:</strong> {html.escape(record.validation_status or '—')} · "
        f"<strong>Outcome:</strong> {_format_score(record.outcome_score)} · "
        f"<strong>Trajectory fidelity:</strong> {_format_score(record.trajectory_fidelity)}</p>"
        f"<p><strong>Ranking:</strong> {ranking} · "
        f"<strong>Citations:</strong> {record.citation_count} · "
        f"<strong>Flags:</strong> {html.escape(flags_txt)}</p>"
        f"{structural}{failure}"
        f"<p><strong>Agent answer:</strong></p>"
        f"<pre class='answer-block'>{html.escape(answer_body)}</pre>"
        f"<p><strong>Judge scores:</strong></p>"
        f"{_render_rubric_scores_html(record.rubric_scores)}"
        f"<p><strong>Judge rationale:</strong></p>"
        f"<pre class='answer-block'>{html.escape(record.judge_rationale or '—')}</pre>"
        f"<p><strong>Trajectory:</strong> {html.escape(record.trajectory_ref)} · "
        f"<strong>Source:</strong> <code>{html.escape(record.source_path)}</code></p>"
        f"</div>"
    )


def _render_variant_summary_cell(record: ItemResultRecord | None) -> str:
    if record is None:
        return "<td class='variant-cell missing'>—</td>"
    classes = ["variant-cell", _status_class(record.judge_status)]
    for flag in record.flags:
        if flag in {"binding_miss", "high_delta"}:
            classes.append(f"flag-{flag}")
    outcome = _format_score(record.outcome_score, digits=2)
    ndcg = _format_score(record.ndcg_at_10, digits=2)
    mrr = _format_score(record.mrr, digits=2)
    judge = html.escape(record.judge_status or "—")
    return (
        f"<td class=\"{' '.join(classes)}\" data-variant=\"{html.escape(record.variant_id)}\" "
        f"data-status=\"{html.escape(record.judge_status)}\">"
        f"<span class='metric-line'>outcome {outcome}</span>"
        f"<span class='metric-line'>ndcg {ndcg} · mrr {mrr}</span>"
        f"<span class='metric-line judge-line'>{judge}</span></td>"
    )


def _render_drilldown_html(
    bundle: ReproOutputBundle,
    *,
    max_item_rows: int = 0,
) -> str:
    if not bundle.variant_results:
        return ""

    variants = _variant_display_order(bundle)
    by_item = _item_records_by_id(bundle)
    item_ids = sorted(by_item.keys())

    profiles = sorted(
        {
            (rec.inspiration_profile or bundle.item_metadata.get(iid, {}).get("inspiration_profile", ""))
            for iid, recs in by_item.items()
            for rec in recs.values()
            if rec.inspiration_profile
        }
        | {
            bundle.item_metadata[iid].get("inspiration_profile", "")
            for iid in item_ids
            if iid in bundle.item_metadata and bundle.item_metadata[iid].get("inspiration_profile")
        }
    )

    parts = [
        '<section id="drilldown"><h2>Item drill-down</h2>',
        "<p>One row per benchmark item; variant columns show outcome, ranking, and judge status "
        "for side-by-side comparison. Expand detail for full evaluation payloads.</p>",
        '<div class="filters">',
        '<label>Highlight variant <select id="filter-variant"><option value="all">All</option>',
    ]
    parts.extend(f'<option value="{html.escape(v)}">{html.escape(v)}</option>' for v in variants)
    parts.append('</select></label>')
    parts.append('<label>Profile <select id="filter-profile"><option value="all">All</option>')
    parts.extend(f'<option value="{html.escape(p)}">{html.escape(p)}</option>' for p in profiles)
    parts.append('</select></label>')
    parts.append(
        '<label>Judge status <select id="filter-judge-status">'
        '<option value="all">All</option>'
        '<option value="ok">ok</option>'
        '<option value="degraded">degraded</option>'
        '<option value="pending">pending</option>'
        '<option value="not_evaluable">not_evaluable</option>'
        "</select></label>"
    )
    parts.append("</div>")
    parts.append('<div class="filters">')
    for st in ("all", "degraded", "pending", "not_evaluable"):
        label = st if st != "all" else "All statuses"
        active = " active" if st == "all" else ""
        parts.append(
            f'<button type="button" class="chip{active}" data-filter-status="{st}">{label}</button>'
        )
    parts.append("</div>")

    header = (
        "<thead><tr><th>Item</th><th>Profile</th><th>Question</th>"
        + "".join(f"<th>{html.escape(v)}</th>" for v in variants)
        + "<th>Detail</th></tr></thead><tbody>"
    )
    parts.append(f"<div class='drilldown-wrap'><table class='drilldown-table'>{header}")

    row_count = 0
    truncated = False
    for item_id in item_ids:
        if max_item_rows > 0 and row_count >= max_item_rows:
            truncated = True
            break
        row_count += 1
        recs = by_item[item_id]
        sample = next(iter(recs.values()))
        meta = bundle.item_metadata.get(item_id, {})
        profile = sample.inspiration_profile or meta.get("inspiration_profile", "") or "—"
        question = sample.question or meta.get("question", "") or "—"
        expected = sample.expected_answer or meta.get("expected_answer", "") or "—"
        question_short = question if len(question) <= 120 else question[:117] + "…"

        statuses = sorted({r.judge_status for r in recs.values() if r.judge_status})
        status_attr = ",".join(statuses)
        row_classes = ["item-row"]
        if any(r.judge_status in HIGHLIGHT_STATUSES for r in recs.values()):
            row_classes.append("has-highlight-status")
        for rec in recs.values():
            for flag in rec.flags:
                if flag in {"binding_miss", "high_delta"}:
                    row_classes.append(f"flag-{flag}")

        variant_cells = "".join(_render_variant_summary_cell(recs.get(vid)) for vid in variants)
        variant_panels = "".join(_render_variant_detail_panel(recs.get(vid), vid) for vid in variants)

        parts.append(
            f"<tr id=\"item-{html.escape(item_id)}\" class=\"{' '.join(row_classes)}\" "
            f"data-profile=\"{html.escape(profile if profile != '—' else '')}\" "
            f"data-statuses=\"{html.escape(status_attr)}\">"
            f"<td class='item-id'>{html.escape(item_id)}</td>"
            f"<td>{html.escape(profile)}</td>"
            f"<td class='question-cell' title=\"{html.escape(question)}\">"
            f"{html.escape(question_short)}</td>"
            f"{variant_cells}"
            f"<td><details class='item-detail-toggle'><summary>Evaluation detail</summary>"
            f"<div class='item-detail'>"
            f"<p><strong>Question:</strong> {html.escape(question)}</p>"
            f"<p><strong>Expected answer:</strong></p>"
            f"<pre class='answer-block'>{html.escape(expected)}</pre>"
            f"<div class='variant-compare'>{variant_panels}</div>"
            f"</div></details></td></tr>"
        )

    if truncated:
        colspan = 3 + len(variants) + 1
        parts.append(
            f"<tr><td colspan='{colspan}'><em>Showing first {max_item_rows} items "
            f"(use --max-item-rows 0 for all).</em></td></tr>"
        )

    parts.append("</tbody></table></div></section>")
    return "".join(parts)


def render_html_report(
    bundle: ReproOutputBundle,
    output_path: Path,
    *,
    table_ids: list[PaperTableId] | None = None,
    max_item_rows: int = 0,
    delta_threshold: float = DEFAULT_DELTA_THRESHOLD,
) -> ReportArtifact:
    compute_investigation_flags(bundle, delta_threshold=delta_threshold)

    summary = build_run_summary(bundle)
    comparison = build_variant_comparison(bundle)
    aggregated_notes = aggregate_investigation_notes(bundle)
    all_views = build_paper_table_views(bundle)
    if table_ids:
        allowed = {t.value for t in table_ids}
        all_views = [v for v in all_views if v.table_id.value in allowed]

    headline_latex = next((v.latex_copy for v in all_views if v.table_id == PaperTableId.HEADLINE), "")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html_out = (
        template.replace("{{RELEASE_TAG}}", html.escape(summary.release_tag))
        .replace("{{WARNINGS}}", _render_warnings_html(bundle.warnings))
        .replace("{{SUMMARY}}", _render_summary_html(summary))
        .replace("{{EXPORT_MANIFEST}}", _render_export_manifest_html(summary))
        .replace("{{OUTCOME_BY_PROFILE}}", "")
        .replace("{{OUTCOME_BY_STRATUM}}", _render_outcome_by_stratum_html(bundle))
        .replace("{{HEADLINE_TEX}}", _render_headline_tex_html(bundle, headline_latex))
        .replace("{{COMPARISON}}", _render_comparison_html(comparison, bundle))
        .replace("{{STRATIFIED}}", "")
        .replace("{{ANOMALIES}}", _render_aggregated_notes_html(aggregated_notes))
        .replace("{{TABLES}}", _render_tables_html(all_views, bundle))
        .replace("{{DRILLDOWN}}", _render_drilldown_html(bundle, max_item_rows=max_item_rows))
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_out, encoding="utf-8")

    return ReportArtifact(
        html_path=output_path,
        generated_at=datetime.now(),
        source_hashes=bundle_source_hashes(bundle),
        format="html",
    )
