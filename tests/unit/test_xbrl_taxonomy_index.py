"""Unit tests for XBRL taxonomy linkbase index (023 M4)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from graph.docling_graph_mapper import map_filing
from models.filing import FilingRef, TableBlock
from models.parsing import ParsedDocument
from parsing.xbrl_taxonomy_index import build_taxonomy_index

FIXTURE_DIR = Path("tests/fixtures/xbrl_taxonomy")


def test_build_taxonomy_index_parses_labels_and_calc() -> None:
    index = build_taxonomy_index(FIXTURE_DIR)
    assert "ProfitLoss" in index
    assert index["ProfitLoss"].standard_label == "Net income (loss)"
    assert "net_income" in index["ProfitLoss"].metric_roles
    assert index["ProfitLoss"].statement_role == "income_statement"
    pretax = index["IncomeLossFromContinuingOperationsBeforeIncomeTaxes"]
    assert pretax.standard_label == "Income before income taxes"
    assert "pretax_income" in pretax.metric_roles
    assert "ProfitLoss" in pretax.calc_children


def test_graph_mapper_attaches_taxonomy_properties() -> None:
    taxonomy_index = {
        concept: meta.model_dump()
        for concept, meta in build_taxonomy_index(FIXTURE_DIR).items()
    }
    filing = FilingRef(
        cik="0000000000",
        accession="0000000000-25-000001",
        form_type="10-K",
        filed_at=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    doc = ParsedDocument(
        filing=filing,
        sections=[],
        tables=[
            TableBlock(
                table_id="xbrl-facts-1",
                headers=[["concept", "value", "period"]],
                rows=[
                    ["ProfitLoss", "value: 100000000"],
                    ["", "period: 2025-01-01 - 2025-12-31"],
                ],
            )
        ],
        footnotes=[],
        parse_confidence=0.9,
        parser_version="test",
        content_hash="abc",
        xbrl_taxonomy_index=taxonomy_index,
    )
    nodes, _, result, _ = map_filing(doc)
    assert result.status.value == "included"
    fact_nodes = [n for n in nodes if n.node_type.value == "CHUNK_XBRL_FACT"]
    assert len(fact_nodes) == 1
    props = fact_nodes[0].properties or {}
    assert props.get("xbrl_standard_label") == "Net income (loss)"
    assert "net_income" in (props.get("xbrl_metric_roles") or "")
