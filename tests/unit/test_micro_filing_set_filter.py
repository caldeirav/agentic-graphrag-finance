"""Verify micro_extractor respects macro filing_set (T022)."""

from datetime import date
from unittest.mock import MagicMock

from graph.legacy_builder import build_snapshot
from models.enums import GraphNodeType, QueryIntent, SourceBias
from models.filing import FilingRef
from models.parsing import ParsedDocument
from models.query import IntentRouterTrace, SectionCandidate
from retrieval.orchestration.nodes.micro_extractor import micro_extractor


def test_micro_only_chunks_from_bound_accession():
    bound = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u",
    )
    other = bound.model_copy(update={"accession": "0000320193-26-000013"})
    docs = [
        ParsedDocument(
            filing=f,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="t",
            content_hash=f.accession,
        )
        for f in (bound, other)
    ]
    snap = build_snapshot("AAPL", docs, snapshot_id="micro-filter")
    from models.enums import IntentSource
    from models.query import IntentRouterTrace as IRT

    snap.nodes.append(
        type(snap.nodes[0])(
            node_id="doc-0000320193-26-000013-xbrl-facts",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="other revenue",
            properties={"excerpt": "other filing revenue"},
            source_ref="x",
        )
    )
    snap.nodes.append(
        type(snap.nodes[0])(
            node_id="doc-0000320193-26-000006-xbrl-facts",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="bound revenue",
            properties={
                "excerpt": "XBRL RevenueFromContract: $1 for period 2025-12-27",
                "accession": bound.accession,
            },
            source_ref="y",
        )
    )

    api = MagicMock()
    api.get_snapshot.return_value = snap
    state = {
        "snapshot_id": snap.snapshot_id,
        "query": "revenue",
        "filing_set": [bound],
        "section_candidates": [
            SectionCandidate(section_node_id="doc-0000320193-26-000006-xbrl-facts", score=1.0)
        ],
        "intent_trace": IRT(
            query_intent=QueryIntent.NUMERIC,
            intent_source=IntentSource.KEYWORD_FALLBACK,
            source_bias_applied=SourceBias.XBRL_PRIMARY,
        ),
    }
    out = micro_extractor(state, graph_api=api)
    for chunk in out.get("evidence_chunks") or []:
        assert bound.accession in chunk.chunk_node_id or chunk.accession == bound.accession
