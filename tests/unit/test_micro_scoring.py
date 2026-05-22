from models.enums import EvidenceSourceType, SourceBias
from retrieval.orchestration.micro_scoring import score_chunk


def test_score_chunk_revenue_xbrl_breakdown() -> None:
    excerpt = (
        "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: "
        "$143.76 billion USD for period 2025-09-28 - 2025-12-28"
    )
    total, components = score_chunk(
        query="Revenue for that quarter?",
        excerpt=excerpt,
        label="",
        node_source=EvidenceSourceType.XBRL,
        is_xbrl_fact=True,
        is_financial_query=True,
        qualitative_only=False,
        section_id="",
        bias=SourceBias.XBRL_PRIMARY,
        anchors=[],
    )
    assert components["concept_match"] is True
    assert components["xbrl_fact_boost"] == 2.0
    assert components["financial_xbrl_boost"] == 3.0
    assert components["bias_multiplier"] == 1.5
    assert total > components["subtotal_before_bias"]
