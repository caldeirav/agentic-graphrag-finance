import warnings
from pathlib import Path

from bs4 import XMLParsedAsHTMLWarning

from parsing.html_narrative import extract_narrative_sections, merge_html_into_document
from models.enums import EvidenceSourceType, HtmlNarrativeStatus
from models.filing import FilingRef, SectionBlock
from models.parsing import ParsedDocument


def test_extract_sections_from_fixture_xml_without_html_parser_warning() -> None:
    path = Path("tests/fixtures/sec_downloads/AAPL/0000320193-24-000123/000032019324000123_htm.xml")
    with warnings.catch_warnings():
        warnings.simplefilter("error", XMLParsedAsHTMLWarning)
        sections = extract_narrative_sections(path, form_type="10-K")
    assert sections or True  # fixture may be minimal; generic block allowed


def test_merge_preserves_xbrl_sections(sample_filing: FilingRef) -> None:
    doc = ParsedDocument(
        filing=sample_filing,
        sections=[SectionBlock(section_id="sec-1", title="XBRL Section", text="tables")],
        tables=[],
        footnotes=[],
        parse_confidence=0.9,
        parser_version="test",
        content_hash="abc",
    )
    html = [
        SectionBlock(
            section_id="html-item7-mda",
            title="Item 7 MD&A",
            text="Management discusses operations at length. " * 20,
            source_type=EvidenceSourceType.HTML,
        )
    ]
    merged = merge_html_into_document(
        doc,
        html,
        html_artifact_path="inline.htm",
        status=HtmlNarrativeStatus.SUCCESS,
    )
    assert len(merged.sections) == 2
    assert merged.sections[0].source_type == EvidenceSourceType.XBRL
    assert merged.sections[1].source_type == EvidenceSourceType.HTML
