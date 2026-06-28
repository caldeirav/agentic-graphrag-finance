"""Extensible XBRL concept → metric role registry (023 catalog v2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

StatementRole = str
MetricRole = str

INCOME_STATEMENT: StatementRole = "income_statement"
BALANCE_SHEET: StatementRole = "balance_sheet"
CASH_FLOW: StatementRole = "cash_flow"
OTHER: StatementRole = "other"


@dataclass(frozen=True)
class ConceptRoleRule:
    """Match an XBRL concept name and attach taxonomy metadata."""

    pattern: re.Pattern[str]
    metric_roles: tuple[MetricRole, ...]
    statement_role: StatementRole = OTHER
    standard_label: str = ""


DEFAULT_CONCEPT_ROLE_RULES: tuple[ConceptRoleRule, ...] = (
    ConceptRoleRule(
        re.compile(r"^(ProfitLoss|NetIncomeLoss)$"),
        ("net_income", "margin_numerator"),
        INCOME_STATEMENT,
        "Net income (loss)",
    ),
    ConceptRoleRule(
        re.compile(r"BeforeIncomeTax|IncomeLossFromContinuingOperationsBefore"),
        ("pretax_income",),
        INCOME_STATEMENT,
        "Income before income taxes",
    ),
    ConceptRoleRule(
        re.compile(
            r"^(Revenues|RevenueFromContractWithCustomerExcludingAssessedTax|"
            r"SalesRevenueNet|TotalRevenuesAndOtherIncome)$"
        ),
        ("revenue", "total_revenue", "margin_denominator"),
        INCOME_STATEMENT,
        "Revenues",
    ),
    ConceptRoleRule(
        re.compile(r"StockholdersEquity|ShareholdersEquity|TotalEquity"),
        ("total_equity",),
        BALANCE_SHEET,
        "Total shareholders' equity",
    ),
    ConceptRoleRule(
        re.compile(r"Assets$|AssetsCurrent|AssetsNoncurrent"),
        ("total_assets",),
        BALANCE_SHEET,
        "Total assets",
    ),
    ConceptRoleRule(
        re.compile(r"Liabilit"),
        ("total_liabilities",),
        BALANCE_SHEET,
        "Total liabilities",
    ),
    ConceptRoleRule(
        re.compile(r"EarningsPerShare|EPS"),
        ("eps",),
        INCOME_STATEMENT,
        "Earnings per share",
    ),
    ConceptRoleRule(
        re.compile(r"NetCashProvidedBy|CashProvidedBy"),
        ("operating_cash_flow",),
        CASH_FLOW,
        "Net cash provided by operating activities",
    ),
)

_extra_rules: list[ConceptRoleRule] = []


def register_concept_role_rules(rules: Iterable[ConceptRoleRule]) -> None:
    """Append custom role rules without modifying defaults."""
    _extra_rules.extend(rules)


def active_concept_role_rules() -> tuple[ConceptRoleRule, ...]:
    return DEFAULT_CONCEPT_ROLE_RULES + tuple(_extra_rules)


def concept_to_standard_label(concept: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", concept)
    return re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)


def infer_concept_taxonomy(concept: str) -> tuple[list[MetricRole], StatementRole, str]:
    for rule in active_concept_role_rules():
        if rule.pattern.search(concept):
            label = rule.standard_label or concept_to_standard_label(concept)
            return list(rule.metric_roles), rule.statement_role, label
    return [], OTHER, concept_to_standard_label(concept)
