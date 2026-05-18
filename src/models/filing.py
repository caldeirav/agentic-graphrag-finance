from datetime import date

from pydantic import BaseModel, Field


class FilingRef(BaseModel):
    cik: str
    accession: str
    form_type: str
    filed_at: date
    period_end: date
    source_uri: str


class CellSpan(BaseModel):
    row_start: int
    row_end: int
    col_start: int
    col_end: int


class SectionBlock(BaseModel):
    section_id: str
    title: str
    level: int = 1
    text: str = ""
    parent_section_id: str | None = None


class TableBlock(BaseModel):
    table_id: str
    headers: list[list[str]]
    rows: list[list[str]]
    merged_cells: list[CellSpan] = Field(default_factory=list)
    footnote_ids: list[str] = Field(default_factory=list)


class FootnoteBlock(BaseModel):
    footnote_id: str
    text: str
    parent_table_id: str | None = None
