"""HTML and copy renderers for reproduction reports (014)."""

from __future__ import annotations

import html
import os
from datetime import datetime
from pathlib import Path

from evaluation.reproduction.report_formatters import (
    build_booktabs_latex,
    format_display_number,
    rows_to_csv,
    rows_to_markdown,
    table_provenance,
)
from evaluation.reproduction.report_loader import bundle_source_hashes
from evaluation.reproduction.report_models import (
    PRIMARY_METRICS,
    STANDARD_VARIANTS,
    ItemResultRecord,
    PaperTableId,
    PaperTableView,
    ReproOutputBundle,
    ReportArtifact,
    RunSummaryView,
    VariantComparisonView,
    VariantCount,
    VariantMetricSeries,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = REPO_ROOT / "templates" / "reproduction_report.html"
DEFAULT_DELTA_THRESHOLD = 0.10
HIGHLIGHT_STATUSES = frozenset({"degraded", "pending", "not_evaluable"})


def build_paper_table_views(bundle: ReproOutputBundle) -> list[PaperTableView]:
    release_tag = bundle.repro_run.release_tag
    views: list[PaperTableView] = []
    for table_id in PaperTableId:
        data = bundle.tables.get(table_id.value)
        if data is None:
            continue
        prov = table_provenance(table_id, data.rows, release_tag)
        views.append(
            PaperTableView(
                table_id=table_id,
                columns=data.columns,
                rows=data.rows,
                latex_copy=build_booktabs_latex(
                    table_id, data.columns, data.rows, release_tag=release_tag, provenance=prov
                ),
                csv_copy=rows_to_csv(data.columns, data.rows),
                markdown_copy=rows_to_markdown(data.columns, data.rows),
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
    for vr in repro.variant_runs:
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
    for vr in repro.variant_runs:
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
        f'<div class="card"><div class="label">{html.escape(l)}</div>'
        f'<div class="value">{html.escape(v)}</div></div>'
        for l, v in cards
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


def _render_comparison_html(comparison: VariantComparisonView) -> str:
    if not comparison.series:
        return ""
    parts = ['<section id="comparison"><h2>Variant comparison</h2>']
    for metric in comparison.metric_names:
        max_val = max((s.values_by_metric.get(metric, 0.0) for s in comparison.series), default=1.0)
        max_val = max_val if max_val > 0 else 1.0
        parts.append(f"<h3>{html.escape(metric)}</h3><div class='bar-chart'>")
        for s in comparison.series:
            val = s.values_by_metric.get(metric, 0.0)
            pct = min(100.0, (val / max_val) * 100.0)
            delta = s.delta_vs_baseline.get(metric)
            delta_txt = f" (Δ {delta:+.3f})" if delta is not None and s.variant_id != comparison.baseline_variant else ""
            parts.append(
                f"<div class='bar-row'><span class='bar-label'>{html.escape(s.variant_id)}</span>"
                f"<div class='bar-track'><div class='bar-fill' style='width:{pct:.1f}%'></div></div>"
                f"<span class='bar-value'>{val:.3f}{delta_txt}</span></div>"
            )
        parts.append("</div>")
    parts.append("</section>")
    return "".join(parts)


def _render_tables_html(views: list[PaperTableView]) -> str:
    parts = ['<section id="paper-tables"><h2>Paper tables</h2>']
    for view in views:
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


def _render_drilldown_html(
    bundle: ReproOutputBundle,
    *,
    max_item_rows: int = 500,
) -> str:
    if not bundle.variant_results:
        return ""

    profiles = sorted(
        {r.inspiration_profile for recs in bundle.variant_results.values() for r in recs if r.inspiration_profile}
    )
    variants = sorted(bundle.variant_results.keys())

    parts = [
        '<section id="drilldown"><h2>Item drill-down</h2>',
        '<div class="filters">',
        '<label>Variant <select id="filter-variant"><option value="all">All</option>',
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

    parts.append(
        "<table><thead><tr><th>Variant</th><th>Item</th><th>Profile</th>"
        "<th>Judge</th><th>Outcome</th><th>Flags</th><th>Detail</th></tr></thead><tbody>"
    )

    row_count = 0
    for variant_id in variants:
        for record in bundle.variant_results[variant_id]:
            if row_count >= max_item_rows:
                break
            row_count += 1
            classes = ["item-row", _status_class(record.judge_status)]
            for flag in record.flags:
                if flag in {"binding_miss", "high_delta"}:
                    classes.append(f"flag-{flag}")
            profile = record.inspiration_profile or "—"
            flags_txt = ", ".join(record.flags) if record.flags else "—"
            parts.append(
                f"<tr class=\"{' '.join(classes)}\" "
                f"data-variant=\"{html.escape(variant_id)}\" "
                f"data-profile=\"{html.escape(record.inspiration_profile)}\" "
                f"data-status=\"{html.escape(record.judge_status)}\">"
                f"<td>{html.escape(variant_id)}</td>"
                f"<td>{html.escape(record.item_id)}</td>"
                f"<td>{html.escape(profile)}</td>"
                f"<td>{html.escape(record.judge_status)}</td>"
                f"<td>{record.outcome_score if record.outcome_score is not None else '—'}</td>"
                f"<td>{html.escape(flags_txt)}</td>"
                f"<td><details><summary>Expand</summary>"
                f"<p><strong>Answer excerpt:</strong> {html.escape(record.answer_excerpt)}</p>"
                f"<p><strong>Citations:</strong> {record.citation_count}</p>"
                f"<p><strong>Trajectory:</strong> {html.escape(record.trajectory_ref)}</p>"
                f"<p><strong>Source:</strong> <code>{html.escape(record.source_path)}</code></p>"
                f"</details></td></tr>"
            )
        if row_count >= max_item_rows:
            break

    if row_count >= max_item_rows:
        parts.append(
            f"<tr><td colspan='7'><em>Showing first {max_item_rows} rows "
            f"(use --max-item-rows to adjust).</em></td></tr>"
        )

    parts.append("</tbody></table></section>")
    return "".join(parts)


def render_html_report(
    bundle: ReproOutputBundle,
    output_path: Path,
    *,
    table_ids: list[PaperTableId] | None = None,
    max_item_rows: int = 500,
    delta_threshold: float = DEFAULT_DELTA_THRESHOLD,
) -> ReportArtifact:
    compute_investigation_flags(bundle, delta_threshold=delta_threshold)

    summary = build_run_summary(bundle)
    comparison = build_variant_comparison(bundle)
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
        .replace("{{HEADLINE_TEX}}", _render_headline_tex_html(bundle, headline_latex))
        .replace("{{COMPARISON}}", _render_comparison_html(comparison))
        .replace("{{TABLES}}", _render_tables_html(all_views))
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
