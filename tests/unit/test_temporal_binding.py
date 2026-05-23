"""Temporal binding against multi-filing snapshot."""

from datetime import date

import pytest

from graph.legacy_builder import build_snapshot
from models.corpus import CorpusTemporalScope
from models.parsing import ParsedDocument
from retrieval.temporal import bind_filings_for_query


def _two_doc_snapshot(sample_filing):
    f1 = sample_filing
    f2 = sample_filing.model_copy(
        update={
            "accession": "0000320193-24-000076",
            "form_type": "10-Q",
            "period_end": date(2024, 6, 29),
        }
    )
    d1 = ParsedDocument(
        filing=f1,
        sections=[],
        tables=[],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash="a",
    )
    d2 = ParsedDocument(
        filing=f2,
        sections=[],
        tables=[],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash="b",
    )
    return build_snapshot("AAPL", [d1, d2], snapshot_id="bind-test")


def test_latest_annual_binding(sample_filing):
    snap = _two_doc_snapshot(sample_filing)
    binding = bind_filings_for_query(
        CorpusTemporalScope(anchor="latest_annual"),
        snap,
    )
    assert len(binding.bound_filings) == 1
    assert binding.bound_filings[0].form_type == "10-K"


def test_prior_quarter_binding(sample_filing):
    snap = _two_doc_snapshot(sample_filing)
    binding = bind_filings_for_query(
        CorpusTemporalScope(anchor="prior_quarter"),
        snap,
    )
    assert len(binding.bound_filings) == 1
    assert binding.bound_filings[0].form_type == "10-Q"


def test_prior_quarter_binds_second_latest_by_period_end():
    """prior_quarter = latest 10-Q minus one period-of-report (not calendar guess)."""
    from datetime import date

    from graph.legacy_builder import build_snapshot
    from models.filing import FilingRef
    from models.parsing import ParsedDocument

    latest = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000013",
        form_type="10-Q",
        filed_at=date(2026, 5, 1),
        period_end=date(2026, 3, 28),
        source_uri="u1",
    )
    prior = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u2",
    )
    ten_k = latest.model_copy(
        update={
            "accession": "0000320193-25-000079",
            "form_type": "10-K",
            "period_end": date(2025, 9, 27),
            "filed_at": date(2025, 10, 31),
        }
    )
    docs = [
        ParsedDocument(
            filing=r,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="test",
            content_hash=r.accession,
        )
        for r in (ten_k, latest, prior)
    ]
    snap = build_snapshot("AAPL", docs, snapshot_id="prior-q-test")
    binding = bind_filings_for_query(
        CorpusTemporalScope(anchor="prior_quarter"),
        snap,
    )
    assert len(binding.bound_filings) == 1
    assert binding.bound_filings[0].accession == "0000320193-26-000006"
