"""Python numeric computation from XBRL catalog entries (021)."""

from __future__ import annotations

import re

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.structured_answer import StructuredAnswerPayload
from retrieval.skills.temporal_scope import TemporalScopeIntent, xbrl_period_matches_intent
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family
from retrieval.skills.ratio_entry_roles import assign_ratio_pair_for_query
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult

_BILLION = re.compile(r"([\d,.]+)\s*billion", re.I)
_MILLION = re.compile(r"([\d,.]+)\s*million", re.I)
_PLAIN = re.compile(r"([\d,.]+)")


def parse_display_value(text: str) -> float | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _BILLION.search(raw)
    if m:
        return float(m.group(1).replace(",", "")) * 1_000_000_000
    m = _MILLION.search(raw)
    if m:
        return float(m.group(1).replace(",", "")) * 1_000_000
    m = _PLAIN.search(raw.replace("$", ""))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _format_value(value: float, *, as_percent: bool = False) -> str:
    if as_percent:
        return f"{value:.2f}%"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f} billion"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f} million"
    if abs(value) >= 1_000:
        return f"{value:,.0f}"
    return f"{value:.2f}"


def format_numeric_display(value: float, *, as_percent: bool = False) -> str:
    """Public wrapper for structured/HTML numeric rendering."""
    return _format_value(value, as_percent=as_percent)


def _entries_by_id(
    catalog: list[XbrlFactCatalogEntry],
    resolution: XbrlFactResolutionResult,
) -> list[XbrlFactCatalogEntry]:
    by_id = {e.chunk_id: e for e in catalog}
    out = [by_id[cid] for cid in resolution.selected_chunk_ids if cid in by_id]
    return out or list(catalog[: resolution.selected_chunk_ids and len(resolution.selected_chunk_ids) or 1])


def _entries_pass_gates(
    entries: list[XbrlFactCatalogEntry],
    query: str,
    metric_intent: MetricIntent,
    temporal_intent: TemporalScopeIntent | None,
) -> bool:
    guard_family = query_concept_family(query, metric_intent)
    for entry in entries:
        if guard_family and not concept_passes_guard(
            entry.concept,
            guard_family,
            segment_in_excerpt=bool(entry.segment_hint),
        ):
            return False
        if temporal_intent and not xbrl_period_matches_intent(
            period_start=entry.period_start,
            period_end=entry.period_end,
            is_annual=entry.is_annual,
            intent=temporal_intent,
        ):
            return False
    return True


def _compute_ratio_payload(
    metric_intent: MetricIntent,
    selected: list[XbrlFactCatalogEntry],
    *,
    fiscal_period: str,
    query: str = "",
) -> StructuredAnswerPayload:
    if len(selected) < 2:
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or "ratio",
            value="n/a",
            citation_chunk_ids=[e.chunk_id for e in selected],
            confidence="low",
            abstain=True,
            abstain_reason="Ratio resolution must provide numerator and denominator facts.",
            metric_type="ratio",
        )
    pair = assign_ratio_pair_for_query(selected, query, metric_intent)
    if pair is None:
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or "ratio",
            value="n/a",
            citation_chunk_ids=[e.chunk_id for e in selected],
            confidence="low",
            abstain=True,
            abstain_reason="Could not assign numerator and denominator roles for ratio pair.",
            metric_type="ratio",
        )
    num_e, den_e = pair
    v_num = parse_display_value(num_e.value_display)
    v_den = parse_display_value(den_e.value_display)
    if v_num is None or v_den is None or v_den == 0:
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or "ratio",
            value="n/a",
            citation_chunk_ids=[num_e.chunk_id, den_e.chunk_id],
            confidence="low",
            abstain=True,
            abstain_reason="Could not parse ratio pair values.",
            metric_type="ratio",
        )
    result = v_num / abs(v_den) * 100.0
    rendered = _format_value(result, as_percent=True)
    return StructuredAnswerPayload(
        metric_label=metric_intent.metric_label or "ratio",
        value=rendered,
        unit="percent",
        fiscal_period=fiscal_period or num_e.period_end,
        citation_chunk_ids=[num_e.chunk_id, den_e.chunk_id],
        confidence="high",
        abstain=False,
        metric_type="ratio",
        formula=f"{num_e.concept}/{den_e.concept}*100",
        computed_value=rendered,
        inputs=[
            {
                "chunk_id": num_e.chunk_id,
                "concept": num_e.concept,
                "period_end": num_e.period_end,
                "value": num_e.value_display,
            },
            {
                "chunk_id": den_e.chunk_id,
                "concept": den_e.concept,
                "period_end": den_e.period_end,
                "value": den_e.value_display,
            },
        ],
    )


def compute_numeric_answer(
    metric_intent: MetricIntent,
    resolution: XbrlFactResolutionResult,
    catalog: list[XbrlFactCatalogEntry],
    *,
    fiscal_period: str = "",
    query: str = "",
    temporal_intent: TemporalScopeIntent | None = None,
) -> StructuredAnswerPayload | None:
    if not resolution.sufficient or not catalog:
        return None
    selected = _entries_by_id(catalog, resolution)
    if not selected:
        return None
    if query and metric_intent.metric_type != "ratio" and not _entries_pass_gates(
        selected, query, metric_intent, temporal_intent
    ):
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or "computation",
            value="n/a",
            citation_chunk_ids=[e.chunk_id for e in selected],
            confidence="low",
            abstain=True,
            abstain_reason="Selected facts fail concept or period guard for the question.",
            metric_type=metric_intent.metric_type,
        )

    if metric_intent.metric_type == "ratio":
        if query and not _entries_pass_gates(selected, query, metric_intent, temporal_intent):
            return StructuredAnswerPayload(
                metric_label=metric_intent.metric_label or "ratio",
                value="n/a",
                citation_chunk_ids=[e.chunk_id for e in selected],
                confidence="low",
                abstain=True,
                abstain_reason="Selected ratio facts fail concept or period guard for the question.",
                metric_type="ratio",
            )
        return _compute_ratio_payload(
            metric_intent,
            selected,
            fiscal_period=fiscal_period,
            query=query,
        )

    if metric_intent.metric_type == "point" or metric_intent.periods_needed == 1:
        best = selected[0]
        val = parse_display_value(best.value_display)
        if val is None:
            return StructuredAnswerPayload(
                metric_label=metric_intent.metric_label or best.concept,
                value=best.value_display,
                concept=best.concept,
                fiscal_period=fiscal_period or best.period_end,
                citation_chunk_ids=[best.chunk_id],
                confidence="medium",
                abstain=False,
                metric_type="point",
                inputs=[
                    {
                        "chunk_id": best.chunk_id,
                        "concept": best.concept,
                        "period_end": best.period_end,
                        "value": best.value_display,
                    }
                ],
            )
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or best.concept,
            value=_format_value(val),
            concept=best.concept,
            fiscal_period=fiscal_period or best.period_end,
            citation_chunk_ids=[best.chunk_id],
            confidence="high",
            abstain=False,
            metric_type="point",
            unit="USD",
            inputs=[
                {
                    "chunk_id": best.chunk_id,
                    "concept": best.concept,
                    "period_end": best.period_end,
                    "value": best.value_display,
                }
            ],
            computed_value=_format_value(val),
        )

    if len(selected) < 2 and len(catalog) >= 2:
        annual = sorted(
            [e for e in catalog if e.is_annual or e.period_end],
            key=lambda e: e.period_end,
            reverse=True,
        )
        if len(annual) >= 2:
            selected = annual[:2]

    if len(selected) < 2:
        return StructuredAnswerPayload(
            metric_label=metric_intent.metric_label or "computation",
            value="n/a",
            citation_chunk_ids=[e.chunk_id for e in selected],
            confidence="low",
            abstain=True,
            abstain_reason="Need two period facts for delta/ratio/percent change.",
            metric_type=metric_intent.metric_type,
        )

    new_e, old_e = selected[0], selected[1]
    v_new = parse_display_value(new_e.value_display)
    v_old = parse_display_value(old_e.value_display)
    if v_new is None or v_old is None:
        return None

    if metric_intent.metric_type == "delta":
        result = v_new - v_old
        formula = "current - prior"
    elif metric_intent.metric_type == "percent_change":
        if v_old == 0:
            return None
        result = (v_new - v_old) / abs(v_old) * 100.0
        formula = "(new-old)/abs(old)*100"
    else:
        if v_old == 0:
            return None
        result = v_new / v_old * 100.0
        formula = "numerator/denominator*100"

    as_pct = metric_intent.metric_type in ("percent_change", "ratio")
    rendered = _format_value(result, as_percent=as_pct)
    return StructuredAnswerPayload(
        metric_label=metric_intent.metric_label or metric_intent.metric_type,
        value=rendered,
        fiscal_period=fiscal_period,
        citation_chunk_ids=[new_e.chunk_id, old_e.chunk_id],
        confidence="high",
        abstain=False,
        metric_type=metric_intent.metric_type,
        formula=formula,
        computed_value=rendered,
        inputs=[
            {
                "chunk_id": new_e.chunk_id,
                "concept": new_e.concept,
                "period_end": new_e.period_end,
                "value": new_e.value_display,
            },
            {
                "chunk_id": old_e.chunk_id,
                "concept": old_e.concept,
                "period_end": old_e.period_end,
                "value": old_e.value_display,
            },
        ],
    )
