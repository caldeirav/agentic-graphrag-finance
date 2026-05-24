from parsing.xbrl_facts import (
    consolidate_xbrl_fact_rows,
    fact_to_excerpt,
    format_xbrl_numeric,
    is_securities_sales_false_positive,
    select_facts_for_index,
    xbrl_concept_matches_query,
)


def test_consolidate_revenue_fact():
    rows = [
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "value: 307003000000"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "period: 2024-09-29 - 2025-09-28"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "currency: USD"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "decimals: -6"],
    ]
    facts = consolidate_xbrl_fact_rows(rows)
    rev = [f for c, f in facts if c == "RevenueFromContractWithCustomerExcludingAssessedTax"]
    assert rev
    assert rev[0]["value"] == "307003000000"


def test_format_revenue_billions():
    formatted = format_xbrl_numeric("307003000000", "-6")
    assert "billion" in formatted
    assert "307" in formatted


def test_select_facts_for_revenue_query():
    rows = [
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "value: 100"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "decimals: -6"],
        ["DocumentType", "value: 10-K"],
        ["DocumentType", "decimals: 0"],
    ]
    facts = consolidate_xbrl_fact_rows(rows)
    selected = select_facts_for_index(facts, query="What was net sales?")
    concepts = [c for c, _ in selected]
    assert any("Revenue" in c for c in concepts)


def test_consolidate_keeps_multiple_periods_per_concept():
    rows = [
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "value: 143760000000"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "period: 2025-09-28 - 2025-12-28"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "decimals: -6"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "value: 124300000000"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "period: 2024-09-29 - 2024-12-29"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "decimals: -6"],
    ]
    facts = consolidate_xbrl_fact_rows(rows)
    rev = [f for c, f in facts if c == "RevenueFromContractWithCustomerExcludingAssessedTax"]
    periods = {f["period"] for f in rev}
    assert "2025-09-28 - 2025-12-28" in periods
    assert "2024-09-29 - 2024-12-29" in periods


def test_xbrl_concept_matches_revenue_not_securities_sales():
    query = "How did total net sales change year over year?"
    assert xbrl_concept_matches_query(
        "RevenueFromContractWithCustomerExcludingAssessedTax", query
    )
    assert not xbrl_concept_matches_query(
        "OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax",
        query,
    )
    assert is_securities_sales_false_positive(
        "ProceedsFromSaleOfAvailableForSaleSecuritiesDebt"
    )


def test_fact_excerpt_readable():
    excerpt = fact_to_excerpt(
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        {
            "value": "307003000000",
            "decimals": "-6",
            "currency": "USD",
            "period": "2024-09-29 - 2025-09-28",
        },
    )
    assert "RevenueFromContract" in excerpt
    assert "billion" in excerpt
