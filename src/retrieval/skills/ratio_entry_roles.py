"""Role-aware numerator/denominator assignment for ratio metrics (023 M4b)."""

from __future__ import annotations

from retrieval.skills.xbrl_concept_guards import query_concept_family
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_taxonomy_catalog import XbrlFactCatalogEntryV2, enrich_catalog_entry

_NUMERATOR_ROLES: dict[str, frozenset[str]] = {
    "margin": frozenset({"net_income", "margin_numerator", "pretax_income"}),
    "tax_rate": frozenset({"tax_expense", "effective_tax"}),
    "dividend_payout": frozenset({"dividend", "dividends_paid"}),
}

_DENOMINATOR_ROLES: dict[str, frozenset[str]] = {
    "margin": frozenset({"revenue", "total_revenue", "margin_denominator"}),
    "tax_rate": frozenset({"pretax_income", "margin_numerator"}),
    "dividend_payout": frozenset({"net_income", "margin_numerator"}),
}


def _as_v2(entry: XbrlFactCatalogEntry | XbrlFactCatalogEntryV2) -> XbrlFactCatalogEntryV2:
    if isinstance(entry, XbrlFactCatalogEntryV2):
        return entry
    return enrich_catalog_entry(entry)


def _role_hit(entry: XbrlFactCatalogEntryV2, roles: frozenset[str], guard_family: str) -> bool:
    if set(entry.metric_roles) & roles:
        return True
    from retrieval.skills.ratio_pair_resolution import _concept_role

    concept_role_by_metric: dict[str, str] = {
        "net_income": "margin_numerator",
        "margin_numerator": "margin_numerator",
        "pretax_income": "margin_numerator",
        "revenue": "margin_denominator",
        "total_revenue": "margin_denominator",
        "margin_denominator": "margin_denominator",
        "tax_expense": "tax_rate_numerator",
        "effective_tax": "tax_rate_numerator",
    }
    for role in roles:
        concept_role = concept_role_by_metric.get(role, role)
        if guard_family == "tax_rate" and role == "pretax_income":
            concept_role = "tax_rate_denominator"
        if _concept_role(entry.concept, concept_role):
            return True
    return False


def assign_ratio_pair_entries(
    entries: list[XbrlFactCatalogEntry | XbrlFactCatalogEntryV2],
    guard_family: str,
) -> tuple[XbrlFactCatalogEntryV2, XbrlFactCatalogEntryV2] | None:
    """Return (numerator, denominator) regardless of input order."""
    if len(entries) != 2:
        return None
    num_roles = _NUMERATOR_ROLES.get(guard_family)
    den_roles = _DENOMINATOR_ROLES.get(guard_family)
    if not num_roles or not den_roles:
        a, b = _as_v2(entries[0]), _as_v2(entries[1])
        return a, b

    a, b = _as_v2(entries[0]), _as_v2(entries[1])
    a_num = _role_hit(a, num_roles, guard_family)
    a_den = _role_hit(a, den_roles, guard_family)
    b_num = _role_hit(b, num_roles, guard_family)
    b_den = _role_hit(b, den_roles, guard_family)

    if a_num and b_den and not (a_den and b_num):
        return a, b
    if b_num and a_den and not (b_den and a_num):
        return b, a
    if a_num and b_den:
        return a, b
    if b_num and a_den:
        return b, a
    if a_den and not a_num:
        return b, a
    if b_den and not b_num:
        return a, b
    if a_num and not a_den:
        return a, b
    if b_num and not b_den:
        return b, a
    return None


def assign_ratio_pair_for_query(
    entries: list[XbrlFactCatalogEntry | XbrlFactCatalogEntryV2],
    query: str,
    metric_intent,
) -> tuple[XbrlFactCatalogEntryV2, XbrlFactCatalogEntryV2] | None:
    guard_family = query_concept_family(query, metric_intent)
    if not guard_family:
        return None
    return assign_ratio_pair_entries(entries, guard_family)
