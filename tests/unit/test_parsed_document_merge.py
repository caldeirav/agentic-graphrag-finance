from models.enums import EvidenceSourceType, HtmlNarrativeStatus
from models.filing import SectionBlock
from parsing.html_narrative import merge_html_into_document


def test_single_artifact_no_sidecar(sample_parsed_document) -> None:
    html = [
        SectionBlock(
            section_id="html-1",
            title="Risk",
            text="risk text " * 50,
            source_type=EvidenceSourceType.HTML,
        )
    ]
    merged = merge_html_into_document(
        sample_parsed_document,
        html,
        html_artifact_path="narrative.htm",
        status=HtmlNarrativeStatus.SUCCESS,
    )
    xbrl_ids = [s.section_id for s in merged.sections if s.source_type == EvidenceSourceType.XBRL]
    assert "sec-1" in xbrl_ids
    assert not any(s.section_id.startswith("html-") for s in merged.sections if s.source_type == EvidenceSourceType.XBRL)
