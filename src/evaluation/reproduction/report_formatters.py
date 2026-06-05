"""Display and copy formatters for reproduction reports (014)."""

from __future__ import annotations

import csv
import io
from typing import Any

from evaluation.reproduction.report_models import STANDARD_VARIANTS, PaperTableId

_META_COLUMNS = ("item_count", "excluded_incomplete", "excluded_degraded")
_NUMERIC_HEADLINE_COLUMNS = frozenset({"value", "delta", *_META_COLUMNS})

_LATEX_ESCAPE_ORDER = ("\\", "&", "%", "$", "#", "_", "{", "}", "~", "^")


def escape_latex(text: str) -> str:
    """Escape user-facing text for LaTeX tabular cells."""
    out = text
    for ch in _LATEX_ESCAPE_ORDER:
        if ch == "\\":
            out = out.replace(ch, "\\textbackslash{}")
        elif ch == "~":
            out = out.replace(ch, "\\textasciitilde{}")
        elif ch == "^":
            out = out.replace(ch, "\\textasciicircum{}")
        else:
            out = out.replace(ch, f"\\{ch}")
    return out


def format_display_number(value: str) -> str:
    """Deterministic display formatting; source CSV values stay unchanged in csv_copy."""
    if value == "":
        return ""
    try:
        num = float(value)
    except ValueError:
        return value
    if num == int(num) and abs(num) < 1e15:
        return str(int(num)) if num == int(num) else f"{num:.4g}"
    return f"{num:.4g}"


def rows_to_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in columns})
    return buf.getvalue().rstrip() + "\n"


def rows_to_markdown(columns: list[str], rows: list[dict[str, str]]) -> str:
    if not columns:
        return ""
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(format_display_number(row.get(col, "")) for col in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, sep, *body]) + "\n"


def build_booktabs_latex(
    table_id: PaperTableId,
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    release_tag: str,
    provenance: dict[str, Any],
) -> str:
    """Paste-ready booktabs table with provenance comments."""
    item_count = provenance.get("item_count", "")
    exclusions = provenance.get("exclusions", "")
    title = table_id.value.replace("_", " ").title()
    lines = [
        f"% release_tag: {release_tag}",
        f"% table: {table_id.value}",
    ]
    if item_count != "":
        lines.append(f"% item_count: {item_count}")
    if exclusions:
        lines.append(f"% exclusions: {exclusions}")
    col_spec = "l" * len(columns)
    lines.extend(
        [
            "\\begin{table}[t]",
            "\\centering",
            "\\small",
            f"\\begin{{tabular}}{{{col_spec}}}",
            "\\toprule",
            " & ".join(escape_latex(c) for c in columns) + " \\\\",
            "\\midrule",
        ]
    )
    for row in rows:
        cells = []
        for col in columns:
            raw = row.get(col, "")
            if is_numeric_column(col):
                cells.append(format_display_number(raw))
            else:
                cells.append(escape_latex(str(raw)))
        lines.append(" & ".join(cells) + " \\\\")
    cap_parts = [title, f"release {release_tag}"]
    if item_count != "":
        cap_parts.append(f"n={item_count}")
    caption = ", ".join(cap_parts) + "."
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            f"\\caption{{{escape_latex(caption)}}}",
            "\\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def pivot_headline_table(
    rows: list[dict[str, str]],
) -> tuple[list[str], list[dict[str, str]]]:
    """Wide layout for HTML: one row per variant, one column per metric."""
    metrics: list[str] = []
    seen_metrics: set[str] = set()
    meta_by_variant: dict[str, dict[str, str]] = {}
    values: dict[str, dict[str, str]] = {}

    for row in rows:
        vid = row["variant_id"]
        metric = row["metric_name"]
        if metric not in seen_metrics:
            seen_metrics.add(metric)
            metrics.append(metric)
        values.setdefault(vid, {})[metric] = row["value"]
        if vid not in meta_by_variant:
            meta_by_variant[vid] = {k: row.get(k, "") for k in _META_COLUMNS}

    order = [v for v in STANDARD_VARIANTS if v in values]
    order.extend(sorted(v for v in values if v not in order))

    columns = ["variant_id", *_META_COLUMNS, *metrics]
    pivoted: list[dict[str, str]] = []
    for vid in order:
        out = {"variant_id": vid, **meta_by_variant.get(vid, {k: "" for k in _META_COLUMNS})}
        for metric in metrics:
            out[metric] = values.get(vid, {}).get(metric, "—")
        pivoted.append(out)
    return columns, pivoted


def is_numeric_column(col: str) -> bool:
    if col in _NUMERIC_HEADLINE_COLUMNS:
        return True
    return col not in {"variant_id", "baseline_variant", "comparison_variant", "metric_name", "na_reason", "inspiration_profile"}


def table_provenance(
    table_id: PaperTableId,
    rows: list[dict[str, str]],
    release_tag: str,
) -> dict[str, Any]:
    """Derive caption metadata from headline-style rows when available."""
    item_count = ""
    exclusions = ""
    if table_id == PaperTableId.HEADLINE and rows:
        item_count = rows[0].get("item_count", "")
        inc = rows[0].get("excluded_incomplete", "0")
        deg = rows[0].get("excluded_degraded", "0")
        if inc or deg:
            exclusions = f"incomplete={inc}, degraded={deg}"
    elif table_id == PaperTableId.TRAJECTORY_AUDIT and rows:
        pending = sum(int(r.get("excluded_pending_judge", "0") or 0) for r in rows)
        if pending:
            exclusions = f"pending_judge={pending}"
    return {
        "release_tag": release_tag,
        "item_count": item_count,
        "exclusions": exclusions,
    }
