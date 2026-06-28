"""XBRL fact resolution prompt helpers (023 M2/M3)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent


def min_facts_required(metric_intent: MetricIntent | None) -> int:
    if metric_intent is None:
        return 1
    if metric_intent.metric_type in ("ratio", "delta", "percent_change"):
        return 2
    if metric_intent.periods_needed >= 2:
        return 2
    return 1


def resolution_temporal_guidance(
    temporal_intent: TemporalScopeIntent | None,
    *,
    fiscal_period_hints: list[str] | None = None,
) -> str:
    lines: list[str] = []
    if fiscal_period_hints:
        lines.append(f"Target fiscal labels: {', '.join(fiscal_period_hints)}.")
    if temporal_intent and temporal_intent.target_fiscal_year:
        year = temporal_intent.target_fiscal_year
        if temporal_intent.form_preference == "10-K":
            lines.append(
                f"Prefer annual 10-K facts for FY{year} (full-year period ending in {year})."
            )
            lines.append(
                "Do NOT pick Q1/Q2/Q3 interim facts when the question asks for fiscal year, "
                "FY, or annual report."
            )
        elif temporal_intent.form_preference == "10-Q":
            lines.append(f"Prefer interim 10-Q facts aligned to FY{year} quarter context.")
    return "\n".join(lines)


def resolution_selection_instructions(
    metric_intent: MetricIntent | None,
    *,
    forbidden_patterns: list[str],
    temporal_intent: TemporalScopeIntent | None = None,
    fiscal_period_hints: list[str] | None = None,
) -> str:
    min_facts = min_facts_required(metric_intent)
    lines = [
        f"Select exactly {min_facts} catalog fact(s) when sufficient=true.",
        "Each catalog row includes standard_label and metric_roles (e.g. net_income, "
        "pretax_income, revenue, margin_denominator). Prefer standard_label text from "
        "the taxonomy linkbase over camelCase concept names when mapping question phrasing "
        "to roles; pick chunk_ids whose metric_roles match; do not confuse pretax_income "
        "with net_income.",
        "Natural-language labels in the question (e.g. 'Earnings Attributable', "
        "'Total Revenues and Other Income') map to metric_roles, not verbatim XBRL names.",
    ]
    temporal = resolution_temporal_guidance(
        temporal_intent,
        fiscal_period_hints=fiscal_period_hints,
    )
    if temporal:
        lines.append(temporal)
    if metric_intent and metric_intent.metric_type == "ratio":
        lines.append(
            "For ratio metrics return selected_chunk_ids as [numerator_id, denominator_id] "
            "for the same fiscal period."
        )
        if metric_intent.metric_label and "margin" in metric_intent.metric_label.lower():
            lines.append(
                "Net profit margin: numerator=net_income (ProfitLoss/NetIncomeLoss), "
                "denominator=total_revenue or Revenues."
            )
        if metric_intent.metric_label and "tax rate" in metric_intent.metric_label.lower():
            lines.append(
                "Effective tax rate: numerator=IncomeTaxExpense; denominator=pretax income. "
                "Exclude statutory rate and tax reconciliation lines."
            )
    elif min_facts >= 2:
        lines.append(
            "For delta/percent-change metrics return two ids ordered newest period first."
        )
    if forbidden_patterns:
        lines.append(
            "Do NOT select concepts containing: "
            + ", ".join(forbidden_patterns[:12])
            + "."
        )
        lines.append(
            "Also reject EquityOther, OtherComprehensiveIncome, statutory tax rate, "
            "and segment-only operating lines for consolidated metrics."
        )
    lines.append("Set sufficient=false when required facts are missing from the catalog.")
    return "\n".join(lines)
