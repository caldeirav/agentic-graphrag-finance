from parsing.html_narrative import _extract_sections_from_item_boundaries, load_section_patterns


def test_item_1a_risk_section_extracted() -> None:
    text = (
        "Preamble metadata " * 50
        + "ITEM 1A. RISK FACTORS The Company faces supply chain risks and regulatory risks. "
        + "More risk discussion here. " * 100
        + "ITEM 7. MANAGEMENT'S DISCUSSION MD&A content here. " * 50
    )
    sections = _extract_sections_from_item_boundaries(text, load_section_patterns())
    assert len(sections) >= 1
    risk = next(s for s in sections if s.narrative_kind and s.narrative_kind.value == "risk_factors")
    assert "supply chain" in risk.text.lower()
