from pydantic import BaseModel, Field

from models.enums import HtmlNarrativeStatus
from models.filing import FilingRef, FootnoteBlock, SectionBlock, TableBlock


class ParsedDocument(BaseModel):
    filing: FilingRef
    sections: list[SectionBlock]
    tables: list[TableBlock]
    footnotes: list[FootnoteBlock]
    parse_confidence: float = Field(ge=0.0, le=1.0)
    parser_version: str
    content_hash: str
    html_narrative_status: HtmlNarrativeStatus = HtmlNarrativeStatus.NOT_ATTEMPTED
    html_artifact_path: str = ""
