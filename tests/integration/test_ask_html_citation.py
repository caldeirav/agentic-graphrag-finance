import os

from graph.builder import build_snapshot
from graph.store import save_snapshot
from models.enums import EvidenceSourceType, NarrativeSectionKind
from models.filing import SectionBlock
from retrieval.service import QueryService
from contracts.query import QueryRequest


def test_qualitative_ask_includes_html_citation_in_trajectory(
    sample_parsed_document, tmp_path
) -> None:
    os.environ["USE_MOCK_LLM"] = "1"
    doc = sample_parsed_document.model_copy(
        update={
            "sections": list(sample_parsed_document.sections)
            + [
                SectionBlock(
                    section_id="html-item1a-risk",
                    title="Item 1A Risk Factors",
                    text="Supply chain concentration creates material risk. " * 40,
                    source_type=EvidenceSourceType.HTML,
                    narrative_kind=NarrativeSectionKind.RISK_FACTORS,
                )
            ]
        }
    )
    snap = build_snapshot("AAPL", [doc])
    graphs = tmp_path / "graphs"
    save_snapshot(snap, graphs)
    svc = QueryService(graph_base_dir=graphs, issuer_id="AAPL")
    resp = svc.answer(
        QueryRequest(
            query="What are the principal risk factors described in the filing?",
            snapshot_id=snap.snapshot_id,
            metadata={"issuer_id": "AAPL"},
            pre_bound_filings=[doc.filing],
        )
    )
    assert resp.answer is not None
    if resp.answer.citations:
        assert any(
            getattr(c.source_type, "value", str(c.source_type)) == "HTML"
            for c in resp.answer.citations
        )
