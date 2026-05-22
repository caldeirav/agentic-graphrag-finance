from models.enums import EvidenceSourceType, NarrativeSectionKind
from models.filing import SectionBlock
from graph.builder import build_snapshot


def test_graph_nodes_carry_html_source_type(sample_parsed_document) -> None:
    doc = sample_parsed_document.model_copy(
        update={
            "sections": list(sample_parsed_document.sections)
            + [
                SectionBlock(
                    section_id="html-item7-mda",
                    title="Item 7 Management Discussion",
                    text="Management discussion narrative " * 30,
                    source_type=EvidenceSourceType.HTML,
                    narrative_kind=NarrativeSectionKind.MD_AND_A,
                )
            ]
        }
    )
    snap = build_snapshot("AAPL", [doc])
    html_nodes = [n for n in snap.nodes if n.properties.get("source_type") == "HTML"]
    assert len(html_nodes) >= 1
