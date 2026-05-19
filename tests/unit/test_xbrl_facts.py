from parsing.xbrl_facts import (
    consolidate_xbrl_fact_rows,
    fact_to_excerpt,
    format_xbrl_numeric,
    select_facts_for_index,
)


def test_consolidate_revenue_fact():
    rows = [
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "value: 307003000000"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "period: 2024-09-29 - 2025-09-28"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "currency: USD"],
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "decimals: -6"],
    ]
    facts = consolidate_xbrl_fact_rows(rows)
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in facts
    assert facts["RevenueFromContractWithCustomerExcludingAssessedTax"]["value"] == "307003000000"


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
