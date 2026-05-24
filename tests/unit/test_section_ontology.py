"""Unit tests for section ontology tagging."""

from __future__ import annotations

from graph.section_ontology import infer_item_number, infer_narrative_kind, section_node_properties
from models.enums import EvidenceSourceType, NarrativeSectionKind
from models.filing import SectionBlock


def test_section_node_properties_from_narrative_kind():
    sec = SectionBlock(
        section_id="html-md_and_a-2",
        title="Item 7.",
        level=1,
        narrative_kind=NarrativeSectionKind.MD_AND_A,
        source_type=EvidenceSourceType.HTML,
    )
    props = section_node_properties(sec)
    assert props["narrative_kind"] == "md_and_a"
    assert props["item_number"] == "7"


def test_infer_risk_from_section_id():
    kind = infer_narrative_kind(
        section_id="html-risk_factors-1",
        title="Item 1A.",
        source_type=EvidenceSourceType.HTML,
    )
    assert kind == "risk_factors"
    assert infer_item_number(narrative_kind=kind, section_id="html-risk_factors-1", title="Item 1A.") == "1A"
