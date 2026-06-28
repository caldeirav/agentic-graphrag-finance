"""Two-fact ratio resolution for margin, tax rate, dividend payout (022-A).

Deprecated for live synthesis (023 M2): used only under USE_MOCK_LLM=1 mock resolution.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent, xbrl_period_matches_intent
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry

RatioPairKind = Literal["margin", "tax_rate", "dividend_payout"]

_MARGIN_NUM = re.compile(
    r"NetIncome(?:Loss)?|ProfitLoss|IncomeLossFromContinuingOperations|OperatingIncomeLoss",
    re.I,
)
_MARGIN_DEN = re.compile(
    r"RevenueFromContractWithCustomer|Revenues?|SalesRevenueNet|TotalRevenues?",
    re.I,
)
_TAX_NUM = re.compile(r"IncomeTaxExpense|ProvisionForIncomeTax|EffectiveIncomeTax", re.I)
_TAX_DEN = re.compile(
    r"EarningsBeforeIncomeTax|IncomeBeforeIncomeTax|PretaxIncome|ProfitBeforeTax|"
    r"IncomeLossFromContinuingOperationsBeforeIncomeTax",
    re.I,
)
_DIV_NUM = re.compile(r"Dividends(?:Paid)?|DistributionsTo(?:Shareholders|Stockholders)", re.I)
_DIV_DEN = re.compile(r"NetIncome(?:Loss)?|ProfitLoss", re.I)

_STATUTORY_TAX = re.compile(r"Statutory|Reconciliation|IncomeTaxReconciliation", re.I)


class RatioPairIntent(BaseModel):
    kind: RatioPairKind
    numerator_family: str
    denominator_family: str
    output_unit: str = "percent"
    min_pairs_required: int = 2


class RatioPairResolution(BaseModel):
    numerator_entry: XbrlFactCatalogEntry | None = None
    denominator_entry: XbrlFactCatalogEntry | None = None
    sufficient: bool = False
    abstain_reason: str = ""
    computed_percent: str = ""


def infer_ratio_pair_intent(
    metric_intent: MetricIntent,
    query: str,
) -> RatioPairIntent | None:
    if metric_intent.metric_type != "ratio":
        return None
    family = query_concept_family(query, metric_intent)
    q = query.lower()
    if family == "tax_rate" or "tax rate" in q or "effective tax" in q:
        return RatioPairIntent(
            kind="tax_rate",
            numerator_family="tax_rate_numerator",
            denominator_family="tax_rate_denominator",
        )
    if family == "dividend_payout" or ("dividend" in q and "payout" in q):
        return RatioPairIntent(
            kind="dividend_payout",
            numerator_family="dividend_numerator",
            denominator_family="dividend_denominator",
        )
    if family == "margin" or "margin" in q:
        return RatioPairIntent(
            kind="margin",
            numerator_family="margin_numerator",
            denominator_family="margin_denominator",
        )
    if "ratio" in q or "percentage of" in q or " as a percent" in q:
        return RatioPairIntent(
            kind="margin",
            numerator_family="margin_numerator",
            denominator_family="margin_denominator",
        )
    return None


def _concept_role(concept: str, role: str) -> bool:
    if role == "tax_rate_numerator":
        if _STATUTORY_TAX.search(concept):
            return False
        return bool(_TAX_NUM.search(concept))
    if role == "tax_rate_denominator":
        return bool(_TAX_DEN.search(concept))
    if role == "dividend_numerator":
        return bool(_DIV_NUM.search(concept)) and not re.search(r"OtherComprehensive|Aoci", concept, re.I)
    if role == "dividend_denominator":
        return bool(_DIV_DEN.search(concept)) and not re.search(r"OtherComprehensive|Aoci", concept, re.I)
    if role == "margin_numerator":
        return bool(_MARGIN_NUM.search(concept)) and not re.search(r"OtherComprehensive|SegmentOperating", concept, re.I)
    if role == "margin_denominator":
        return bool(_MARGIN_DEN.search(concept))
    return False


def _entry_score(entry: XbrlFactCatalogEntry, *, prefer_annual: bool) -> float:
    score = 0.0
    if entry.is_annual:
        score += 5.0
    if entry.matches_query:
        score += 2.0
    if prefer_annual and entry.period_end.endswith("-12-31"):
        score += 1.0
    return score


def resolve_ratio_pair(
    catalog: list[XbrlFactCatalogEntry],
    metric_intent: MetricIntent,
    query: str,
    *,
    temporal_intent: TemporalScopeIntent | None = None,
) -> RatioPairResolution:
    pair_intent = infer_ratio_pair_intent(metric_intent, query)
    if pair_intent is None:
        return RatioPairResolution(
            sufficient=False,
            abstain_reason="Question is not a supported ratio pair metric.",
        )

    guard_family = query_concept_family(query, metric_intent)
    candidates: list[XbrlFactCatalogEntry] = []
    for entry in catalog:
        if temporal_intent and not xbrl_period_matches_intent(
            period_start=entry.period_start,
            period_end=entry.period_end,
            is_annual=entry.is_annual,
            intent=temporal_intent,
        ):
            continue
        if guard_family == "dividend_payout":
            if not (
                _concept_role(entry.concept, pair_intent.numerator_family)
                or _concept_role(entry.concept, pair_intent.denominator_family)
            ):
                continue
        elif guard_family and not concept_passes_guard(
            entry.concept,
            guard_family,
            segment_in_excerpt=bool(entry.segment_hint),
        ):
            continue
        candidates.append(entry)

    if not candidates:
        return RatioPairResolution(
            sufficient=False,
            abstain_reason="No catalog entries pass period/concept guards for ratio.",
        )

    numerators = [
        e
        for e in candidates
        if _concept_role(e.concept, pair_intent.numerator_family)
    ]
    denominators = [
        e
        for e in candidates
        if _concept_role(e.concept, pair_intent.denominator_family)
    ]
    if not numerators or not denominators:
        return RatioPairResolution(
            sufficient=False,
            abstain_reason="Missing numerator or denominator fact for ratio computation.",
        )

    best_pair: tuple[XbrlFactCatalogEntry, XbrlFactCatalogEntry] | None = None
    best_score = -1.0
    for num in numerators:
        for den in denominators:
            if num.chunk_id == den.chunk_id:
                continue
            if num.period_end and den.period_end and num.period_end != den.period_end:
                continue
            score = _entry_score(num, prefer_annual=True) + _entry_score(den, prefer_annual=True)
            if score > best_score:
                best_score = score
                best_pair = (num, den)

    if best_pair is None:
        return RatioPairResolution(
            sufficient=False,
            abstain_reason="No matching numerator/denominator pair for the same period.",
        )

    num_e, den_e = best_pair
    return RatioPairResolution(
        numerator_entry=num_e,
        denominator_entry=den_e,
        sufficient=True,
    )


def ratio_pair_to_resolution(pair: RatioPairResolution):
    """Build XbrlFactResolutionResult-compatible chunk id list."""
    from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult

    if not pair.sufficient or not pair.numerator_entry or not pair.denominator_entry:
        return XbrlFactResolutionResult(
            selected_chunk_ids=[],
            rationale=pair.abstain_reason or "Insufficient ratio pair.",
            sufficient=False,
        )
    return XbrlFactResolutionResult(
        selected_chunk_ids=[pair.numerator_entry.chunk_id, pair.denominator_entry.chunk_id],
        rationale="Ratio pair: numerator and denominator for same annual period.",
        sufficient=True,
    )
