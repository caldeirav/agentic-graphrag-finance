"""Unit test: xbrl_only ablation filters HTML narrative chunks (012)."""

from unittest.mock import MagicMock

from models.enums import EvidenceSourceType
from models.query import EvidenceChunk
from retrieval.orchestration.nodes.micro_extractor import micro_extractor


def _chunk(chunk_id: str, source: EvidenceSourceType) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt="text",
        content_hash="sha256:abc",
        source_type=source,
    )


def test_xbrl_only_excludes_html_chunks() -> None:
    state = {
        "variant_xbrl_only": True,
        "evidence_chunks": [],
    }
    graph_api = MagicMock()
    xbrl = _chunk("x1", EvidenceSourceType.XBRL)
    html = _chunk("h1", EvidenceSourceType.HTML)

    def fake_micro(_state, *, graph_api):
        return {"evidence_chunks": [xbrl, html]}

    import retrieval.orchestration.nodes.micro_extractor as mod

    original = mod.run_micro_navigation
    mod.run_micro_navigation = fake_micro
    try:
        out = micro_extractor(state, graph_api=graph_api)
    finally:
        mod.run_micro_navigation = original

    ids = [c.chunk_node_id for c in out["evidence_chunks"]]
    assert ids == ["x1"]


def test_xbrl_only_false_keeps_html() -> None:
    state = {"variant_xbrl_only": False}
    graph_api = MagicMock()
    chunks = [_chunk("x1", EvidenceSourceType.XBRL), _chunk("h1", EvidenceSourceType.HTML)]

    def fake_micro(_state, *, graph_api):
        return {"evidence_chunks": chunks}

    import retrieval.orchestration.nodes.micro_extractor as mod

    original = mod.run_micro_navigation
    mod.run_micro_navigation = fake_micro
    try:
        out = micro_extractor(state, graph_api=graph_api)
    finally:
        mod.run_micro_navigation = original

    assert len(out["evidence_chunks"]) == 2
