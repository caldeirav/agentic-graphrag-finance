"""Expand repro slice accessions for YoY/comparison items (022-C)."""

from __future__ import annotations

import re

from graph.store import load_snapshot
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent

_YOY_RE = re.compile(
    r"year[- ]over[- ]year|year over year|\byoy\b|compared to (?:the )?prior|"
    r"prior year|previous year|two fiscal years",
    re.I,
)


def _needs_comparison_filings(
    query: str,
    temporal_intent: TemporalScopeIntent | None,
    metric_intent: MetricIntent | None,
) -> bool:
    if metric_intent and metric_intent.metric_type in ("delta", "percent_change"):
        return True
    if metric_intent and metric_intent.periods_needed >= 2:
        return True
    if temporal_intent and temporal_intent.comparison_mode in ("yoy", "YOY", "YoY"):
        return True
    return bool(_YOY_RE.search(query))


def expand_slice_accessions(
    accessions: list[str],
    index,
    *,
    query: str = "",
    temporal_intent: TemporalScopeIntent | None = None,
    metric_intent: MetricIntent | None = None,
) -> list[str]:
    """Include prior-year 10-K accessions from the same issuer snapshot when needed."""
    expanded = list(dict.fromkeys(accessions))
    if not expanded or not _needs_comparison_filings(query, temporal_intent, metric_intent):
        return expanded

    target_year = temporal_intent.target_fiscal_year if temporal_intent else None
    if target_year is None:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", query)]
        target_year = max(years) if years else None
    prior_year = (target_year - 1) if target_year else None
    if prior_year is None:
        return expanded

    try:
        refs = index.resolve_accessions("slice-expand", expanded)
    except Exception:
        return expanded

    for ref in refs:
        try:
            snapshot = load_snapshot(ref.ticker, ref.snapshot_id, index.graphs_dir)
        except Exception:
            continue
        for filing in snapshot.manifest.filing_refs:
            if filing.form_type != "10-K":
                continue
            pe = filing.period_end
            if pe and pe.year == prior_year and filing.accession not in expanded:
                expanded.append(filing.accession)
    return expanded
