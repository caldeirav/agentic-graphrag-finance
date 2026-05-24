"""Accession resolution in trajectory export (010)."""

from datetime import date

from evaluation.validator.trajectory import validate_trajectory
from models.enums import QueryStatus
from models.evaluation import ValidationStatus
from models.filing import FilingRef
from models.query import EvidenceChunk, MacroPlan, TemporalScope
from tracing.trajectory_export import build_agent_trajectory_snapshot

_AAPL_25 = "0000320193-25-000079"
_AAPL_24 = "0000320193-24-000123"


def _filing(accession: str, *, period_end: date) -> FilingRef:
    return FilingRef(
        cik="0000320193",
        accession=accession,
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=period_end,
        source_uri="https://example.com",
    )


def test_doc_prefixed_chunk_resolves_full_accession():
    state = {
        "query_id": "q-yoy",
        "query": "YoY net sales",
        "macro_plan": MacroPlan(
            intent_summary="compare sales",
            temporal_scope=TemporalScope(anchor_periods=[]),
        ),
        "filing_set": [
            _filing(_AAPL_25, period_end=date(2025, 9, 27)),
            _filing(_AAPL_24, period_end=date(2024, 9, 28)),
        ],
        "graph_traversal": [
            {"node_id": "macro", "stage": "macro"},
            {"node_id": f"doc-{_AAPL_25}-xbrl-facts", "stage": "meso", "edge_type": "CONTAINS"},
            {"node_id": f"doc-{_AAPL_24}-xbrl-facts", "stage": "meso", "edge_type": "CONTAINS"},
        ],
        "evidence_chunks": [
            EvidenceChunk(
                chunk_node_id=f"doc-{_AAPL_25}-xbrl-f31f441fd33c",
                excerpt="net sales",
                content_hash="h1",
                accession="",
            ),
        ],
        "status": QueryStatus.SUCCESS,
    }
    snap = build_agent_trajectory_snapshot(state)
    assert len(snap.graph_traversal) == 2
    assert all(h.accession_prefix == _AAPL_25 or h.accession_prefix == _AAPL_24 for h in snap.graph_traversal)
    assert snap.evidence[0].accession == _AAPL_25
    result = validate_trajectory(snap)
    assert result.status != ValidationStatus.NON_REPRODUCIBLE
