"""Micro extractor respects bound filing_set."""

from datetime import date

from graph.builder import build_snapshot
from graph.query_api import LocalGraphQueryAPI
from models.filing import FilingRef, TableBlock
from models.parsing import ParsedDocument
from parsing.docling_xbrl import PARSER_VERSION
from retrieval.orchestration.nodes.meso_router import meso_router
from retrieval.orchestration.nodes.micro_extractor import micro_extractor


def _doc_with_revenue(
    *,
    accession: str,
    period_end: date,
    revenue_value: str,
    period_label: str,
) -> ParsedDocument:
    concept = "RevenueFromContractWithCustomerExcludingAssessedTax"
    rows = [
        [concept, f"value: {revenue_value}"],
        [concept, f"period: {period_label}"],
        [concept, "currency: USD"],
        [concept, "decimals: -6"],
    ]
    return ParsedDocument(
        filing=FilingRef(
            cik="0000320193",
            accession=accession,
            form_type="10-Q",
            filed_at=period_end,
            period_end=period_end,
            source_uri=f"u://{accession}",
        ),
        sections=[],
        tables=[TableBlock(table_id="xbrl-facts-0", headers=[], rows=rows)],
        footnotes=[],
        parse_confidence=1.0,
        parser_version=PARSER_VERSION,
        content_hash=accession,
    )


def test_micro_extractor_only_returns_bound_filing_facts(tmp_path):
    bound = _doc_with_revenue(
        accession="0000320193-26-000006",
        period_end=date(2025, 12, 27),
        revenue_value="95000000000",
        period_label="2025-09-28 - 2025-12-27",
    )
    other = _doc_with_revenue(
        accession="0000320193-25-000057",
        period_end=date(2025, 3, 29),
        revenue_value="124300000000",
        period_label="2024-09-29 - 2024-12-29",
    )
    snap = build_snapshot("AAPL", [bound, other], snapshot_id="micro-scope")
    api = LocalGraphQueryAPI(tmp_path, "AAPL")
    api._cache[snap.snapshot_id] = snap

    state = {
        "snapshot_id": snap.snapshot_id,
        "query": "Revenue in the prior quarter?",
        "filing_set": [bound.filing],
        "section_candidates": [],
    }
    meso = meso_router(state, graph_api=api)
    state["section_candidates"] = meso["section_candidates"]
    out = micro_extractor(state, graph_api=api)

    assert out["evidence_chunks"]
    for chunk in out["evidence_chunks"]:
        assert chunk.chunk_node_id.startswith("doc-0000320193-26-000006")
    excerpts = " ".join(c.excerpt for c in out["evidence_chunks"])
    assert "2024-12-29" not in excerpts
