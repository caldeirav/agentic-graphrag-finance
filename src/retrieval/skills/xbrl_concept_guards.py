"""Strict XBRL concept-family guards for catalog filtering (022)."""

from __future__ import annotations

import re

from retrieval.skills.metric_intent import MetricIntent

_EQUITY_EXCLUDE = re.compile(
    r"EquityOther|OtherComprehensive|FairValue|Member|"
    r"NoncontrollingInterestMember|ParentMember",
    re.I,
)
_EQUITY_PREFERRED = re.compile(
    r"StockholdersEquity(?:IncludingPortionAttributableToNoncontrollingInterest|"
    r"Including|AttributableToParent)?$|"
    r"StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    re.I,
)

_RATIO_TAX_EXCLUDE = re.compile(
    r"AccruedIncomeTax|OtherComprehensive|Reclassification|FairValue|Pension|"
    r"ComprehensiveIncome|DefinedBenefit|Aoci",
    re.I,
)
_RATIO_TAX_NUMERATOR = re.compile(r"IncomeTaxExpense|ProvisionForIncomeTax|EffectiveIncomeTax", re.I)
_RATIO_TAX_DENOMINATOR = re.compile(
    r"EarningsBeforeIncomeTax|IncomeBeforeIncomeTax|PretaxIncome|ProfitBeforeTax",
    re.I,
)

_DIVIDEND_PAYOUT_EXCLUDE = re.compile(
    r"OtherComprehensive|Reclassification|FairValue|Pension|Aoci|Accrued",
    re.I,
)
_DIVIDEND_CONCEPT = re.compile(r"Dividend|DistributionsToShareholders", re.I)

_MARGIN_EXCLUDE = re.compile(
    r"OtherComprehensive|FairValue|Accrued|Reclassification|SegmentOperating",
    re.I,
)

_SEGMENT_REVENUE = re.compile(
    r"Segment.*Revenue|Revenue.*Segment|Sales.*Segment|OperatingRevenue.*Segment",
    re.I,
)
_CONSOLIDATED_REVENUE = re.compile(
    r"RevenueFromContract|NetSales|TotalRevenues?|SalesRevenueNet",
    re.I,
)

_ASSET_CHANGE_EXCLUDE = re.compile(
    r"FairValue|OtherAssetsFairValue|AvailableForSale|Derivative",
    re.I,
)
_ASSETS_PREFERRED = re.compile(r"^Assets$|AssetsCurrent|AssetsNoncurrent", re.I)


def query_concept_family(query: str, metric_intent: MetricIntent | None = None) -> str | None:
    q = query.lower()
    if metric_intent and metric_intent.metric_type == "ratio":
        if "tax rate" in q or "effective tax" in q:
            return "tax_rate"
        if "dividend" in q and ("payout" in q or "ratio" in q):
            return "dividend_payout"
        if "margin" in q:
            return "margin"
    if any(k in q for k in ("shareholder equity", "stockholders equity", "total equity", "shareholders' equity")):
        return "equity"
    if "equity" in q and "shareholder" in q:
        return "equity"
    if "segment" in q or "energy product" in q or "upstream" in q:
        return "segment_revenue"
    if any(k in q for k in ("change in total assets", "change in assets", "asset change")):
        return "assets"
    return None


def concept_passes_guard(concept: str, family: str | None, *, segment_in_excerpt: bool = False) -> bool:
    if not family:
        return True
    if family == "equity":
        if _EQUITY_EXCLUDE.search(concept):
            return False
        return bool(_EQUITY_PREFERRED.search(concept)) or "StockholdersEquity" in concept
    if family == "tax_rate":
        if _RATIO_TAX_EXCLUDE.search(concept):
            return False
        return bool(_RATIO_TAX_NUMERATOR.search(concept) or _RATIO_TAX_DENOMINATOR.search(concept))
    if family == "dividend_payout":
        if _DIVIDEND_PAYOUT_EXCLUDE.search(concept):
            return False
        return bool(_DIVIDEND_CONCEPT.search(concept))
    if family == "margin":
        if _MARGIN_EXCLUDE.search(concept):
            return False
        return bool(re.search(r"Income|Revenue|Profit|Earnings", concept, re.I))
    if family == "segment_revenue":
        if _SEGMENT_REVENUE.search(concept):
            return True
        return segment_in_excerpt and not _CONSOLIDATED_REVENUE.search(concept)
    if family == "assets":
        if _ASSET_CHANGE_EXCLUDE.search(concept):
            return False
        return bool(_ASSETS_PREFERRED.search(concept) or concept == "Assets")
    return True
