"""Consolidate Docling XBRL key-value fact rows into searchable records."""

from __future__ import annotations

import re

# Concepts indexed for graph evidence (financial statement line items).
_PRIORITIZED_CONCEPT = re.compile(
    r"(Revenue|Sales|Income|Earnings|Profit|Assets|Liabilities|Equity|Cash|"
    r"EPS|Margin|Operating|Gross|Net|Debt|Securities|Receivable|Payable|"
    r"Expense|CostOf|Investment|Dividend|Shares|Stock|Depreciation|Amortization)",
    re.IGNORECASE,
)

_QUERY_CONCEPT_HINTS: dict[str, re.Pattern[str]] = {
    "revenue": re.compile(r"Revenue|Sales", re.I),
    "sales": re.compile(r"Revenue|Sales", re.I),
    "income": re.compile(r"Income|Earnings|Profit", re.I),
    "asset": re.compile(r"Assets", re.I),
    "cash": re.compile(r"Cash", re.I),
    "debt": re.compile(r"Debt|Borrow", re.I),
}

_REVENUE_CONCEPT = re.compile(
    r"RevenueFromContract|NetSales|TotalRevenues?|SalesRevenueNet",
    re.I,
)

# "sales" in a query must not match AvailableForSale / proceeds-from-sale line items.
_SECURITIES_SALES_FALSE_POSITIVE = re.compile(
    r"AvailableForSale|ProceedsFromSale|SaleOfStock|SalesTypeLease|"
    r"SecuritiesSold|DebtSecurities.*Sale|SaleMaturity|SaleOfAvailable",
    re.I,
)


def consolidate_xbrl_fact_rows(rows: list[list[str]]) -> list[tuple[str, dict[str, str]]]:
    """Group flat key-value rows into one record per concept value instance (all contexts)."""
    facts: list[tuple[str, dict[str, str]]] = []
    current_concept: str | None = None
    current_fields: dict[str, str] = {}

    def flush() -> None:
        nonlocal current_fields, current_concept
        if current_concept and "value" in current_fields:
            facts.append((current_concept, dict(current_fields)))
        current_fields = {}

    for row in rows:
        if len(row) < 2:
            continue
        left, right = row[0].strip(), row[1].strip()
        if right.startswith("value:"):
            flush()
            current_concept = left or current_concept
            if current_concept:
                current_fields = {"value": right[6:].strip()}
        elif right.startswith("period:"):
            if current_concept:
                current_fields["period"] = right[7:].strip()
        elif right.startswith("currency:"):
            if current_concept:
                current_fields["currency"] = right[9:].strip()
        elif right.startswith("decimals:"):
            if current_concept:
                current_fields["decimals"] = right[9:].strip()
        elif not right.startswith("dimension:") and left:
            current_concept = left
    flush()
    return facts


def format_xbrl_numeric(value: str, decimals: str = "") -> str:
    """Format XBRL numeric fact (decimals=-6 → value is in millions of USD)."""
    try:
        raw = int(value.replace(",", ""))
    except ValueError:
        return value
    try:
        d = int(decimals) if decimals else 0
    except ValueError:
        d = 0
    if d < 0:
        scaled = raw / (10 ** (-d))
    else:
        scaled = float(raw)
    # After decimals adjustment, ``scaled`` is typically in millions for SEC filers.
    if scaled >= 1_000:
        return f"${scaled / 1e3:.2f} billion"
    if scaled >= 1:
        return f"${scaled:.2f} million"
    return f"${scaled:,.0f}"


def fact_to_excerpt(concept: str, fields: dict[str, str]) -> str:
    val = format_xbrl_numeric(fields.get("value", ""), fields.get("decimals", ""))
    period = fields.get("period", "")
    ccy = fields.get("currency", "")
    parts = [f"XBRL {concept}: {val}"]
    if ccy:
        parts.append(ccy)
    if period:
        parts.append(f"for period {period}")
    return " ".join(parts)


def is_prioritized_concept(concept: str) -> bool:
    return bool(_PRIORITIZED_CONCEPT.search(concept))


def concepts_for_query(query: str) -> re.Pattern[str] | None:
    q = query.lower()
    for hint, pattern in _QUERY_CONCEPT_HINTS.items():
        if hint in q:
            return pattern
    return None


def is_revenue_concept(concept: str) -> bool:
    return bool(_REVENUE_CONCEPT.search(concept))


def is_securities_sales_false_positive(concept: str) -> bool:
    return bool(_SECURITIES_SALES_FALSE_POSITIVE.search(concept))


def is_revenue_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in ("revenue", "net sales", "total sales", "sales"))


def xbrl_concept_matches_query(concept: str, query: str) -> bool:
    """Match XBRL taxonomy names to a financial query without securities false positives."""
    if not concept:
        return False
    if is_securities_sales_false_positive(concept):
        return False
    if is_revenue_query(query) and is_revenue_concept(concept):
        return True
    pat = concepts_for_query(query)
    if pat and pat.search(concept):
        return True
    return False


def select_facts_for_index(
    facts: list[tuple[str, dict[str, str]]],
    *,
    query: str | None = None,
    max_facts: int = 400,
) -> list[tuple[str, dict[str, str]]]:
    """Return concept instances to materialize as graph evidence nodes."""
    query_pat = concepts_for_query(query) if query else None
    selected: list[tuple[str, dict[str, str]]] = []
    for concept, fields in facts:
        if "value" not in fields:
            continue
        if query_pat and query_pat.search(concept):
            selected.append((concept, fields))
        elif is_prioritized_concept(concept):
            selected.append((concept, fields))

    def _rank(item: tuple[str, dict[str, str]]) -> tuple[int, str]:
        concept = item[0]
        if query_pat and query_pat.search(concept):
            return (0, concept)
        if re.search(r"RevenueFromContract|NetSales|TotalRevenue", concept, re.I):
            return (1, concept)
        if _PRIORITIZED_CONCEPT.search(concept):
            return (2, concept)
        return (9, concept)

    selected.sort(key=_rank)
    return selected[:max_facts]
