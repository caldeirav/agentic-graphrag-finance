"""Shared navigation eval snapshot (009) — sections, table, footnote chain."""

from __future__ import annotations

from datetime import date

from graph.legacy_builder import build_snapshot as legacy_build_snapshot
from models.enums import EvidenceSourceType, NarrativeSectionKind
from models.filing import FilingRef, FootnoteBlock, SectionBlock, TableBlock
from models.parsing import ParsedDocument
from parsing.docling_xbrl import PARSER_VERSION


def build_navigation_eval_snapshot():
    ref = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://nav-eval",
    )
    doc = ParsedDocument(
        filing=ref,
        sections=[
            SectionBlock(
                section_id="html-md_and_a-0",
                title="Item 7. Management's Discussion and Analysis",
                text="The Company faces risk factors including competition and supply chain in MD&A.",
                level=1,
                source_type=EvidenceSourceType.HTML,
                narrative_kind=NarrativeSectionKind.MD_AND_A,
            ),
            SectionBlock(
                section_id="html-risk_factors-0",
                title="Item 1A. Risk Factors",
                text="Macroeconomic and industry risks may materially affect results.",
                level=1,
                source_type=EvidenceSourceType.HTML,
                narrative_kind=NarrativeSectionKind.RISK_FACTORS,
            ),
            SectionBlock(
                section_id="sec-notes",
                title="Notes to Consolidated Financial Statements",
                text="Summary of significant accounting policies and estimates.",
                level=1,
            ),
            SectionBlock(
                section_id="sec-bs",
                title="Consolidated Balance Sheets",
                text="Assets and liabilities at fiscal year end.",
                level=1,
            ),
        ],
        tables=[
            TableBlock(
                table_id="table-revenue",
                headers=[["", "2024", "2023"]],
                rows=[
                    ["Total net sales", "391,035", "383,285"],
                    ["Products", "298,085", "298,092"],
                ],
                footnote_ids=["fn-rev"],
            ),
            TableBlock(
                table_id="table-assets",
                headers=[["", "2024"]],
                rows=[["Total assets", "352,583"]],
                footnote_ids=[],
            ),
        ],
        footnotes=[
            FootnoteBlock(
                footnote_id="fn-rev",
                text="Revenue is recognized when control transfers to the customer.",
                parent_table_id="table-revenue",
            ),
        ],
        parse_confidence=0.95,
        parser_version=PARSER_VERSION,
        content_hash="nav-eval-v1",
    )
    return legacy_build_snapshot("0000320193", [doc], snapshot_id="nav-eval-001")
