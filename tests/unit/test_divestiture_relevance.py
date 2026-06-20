"""Divestiture relevance label refinement."""

from __future__ import annotations

from datetime import UTC, date, datetime

from evaluation.reproduction.relevance import refine_divestiture_relevance_chunks
from models.enums import GraphNodeType
from models.filing import FilingRef
from models.graph import GraphManifest, GraphNode, GraphSnapshot


def _snapshot() -> GraphSnapshot:
    acc = "0000034088-26-000067"
    mda = f"doc-{acc}-html-md_and_a-4"
    biz = f"doc-{acc}-html-business_description-45"
    nodes = [
        GraphNode(
            node_id=mda,
            node_type=GraphNodeType.CHUNK_PARAGRAPH,
            label="mda chunk",
            source_ref=(
                "During 2025 we received $1.1 billion from divestment activities including "
                "the Singapore retail fuels business and Mobil Argentina S.A."
            ),
        ),
        GraphNode(
            node_id=biz,
            node_type=GraphNodeType.CHUNK_PARAGRAPH,
            label="biz chunk",
            source_ref=(
                "The sale of the Singapore retail fuels business and Mobil Argentina S.A. "
                "contributed to divestment proceeds."
            ),
        ),
    ]
    return GraphSnapshot(
        snapshot_id="snap-1",
        issuer_id="XOM",
        nodes=nodes,
        edges=[],
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[
                FilingRef(
                    cik="0000034088",
                    accession=acc,
                    form_type="10-K",
                    filed_at=date(2026, 2, 1),
                    period_end=date(2025, 12, 31),
                    source_uri="",
                )
            ],
            parser_version="test",
            graph_builder_version="test",
            storage_path=".",
        ),
    )


def test_refine_divestiture_merges_business_description_chunks() -> None:
    snap = _snapshot()
    acc = "0000034088-26-000067"
    base = [f"doc-{acc}-html-md_and_a-4"]
    out = refine_divestiture_relevance_chunks(
        snap,
        base,
        question="What sales were included in divestment activities?",
        gt_answer="Singapore retail fuels business and Mobil Argentina S.A.",
        section_paths=[f"{acc}/ITEM 7. MANAGEMENT'S DISCUSSION"],
    )
    assert f"doc-{acc}-html-business_description-45" in out
