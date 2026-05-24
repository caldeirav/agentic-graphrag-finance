"""Micro scoring prefers revenue concepts over securities 'sales' false positives."""

from models.enums import EvidenceSourceType, SourceBias
from retrieval.orchestration.micro_scoring import score_chunk


def test_revenue_concept_outscores_securities_sales():
    query = "How did total net sales change year over year?"
    rev_score, _ = score_chunk(
        query=query,
        excerpt=(
            "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $416.16 billion USD "
            "for period 2024-09-29 - 2025-09-28"
        ),
        label="RevenueFromContractWithCustomerExcludingAssessedTax",
        node_source=EvidenceSourceType.XBRL,
        is_xbrl_fact=True,
        is_financial_query=True,
        qualitative_only=False,
        section_id="xbrl-facts",
        bias=SourceBias.XBRL_PRIMARY,
        anchors=[],
    )
    sec_score, _ = score_chunk(
        query=query,
        excerpt=(
            "XBRL OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax: "
            "$1.23 billion USD for period 2024-09-29 - 2025-09-28"
        ),
        label="OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax",
        node_source=EvidenceSourceType.XBRL,
        is_xbrl_fact=True,
        is_financial_query=True,
        qualitative_only=False,
        section_id="xbrl-facts",
        bias=SourceBias.XBRL_PRIMARY,
        anchors=[],
    )
    assert rev_score > sec_score
