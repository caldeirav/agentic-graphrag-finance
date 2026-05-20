"""Unit tests for corpus models and cap validation."""

from datetime import date

import pytest

from ingestion.corpus import CorpusCapExceededError, resolve_corpus_members
from models.corpus import CorpusDefinition, CorpusDefinitionMode
from models.ingestion import FilingResolution


def test_corpus_cap_exceeded(monkeypatch):
    defn = CorpusDefinition(
        issuer_id="AAPL",
        mode=CorpusDefinitionMode.DEFAULT_TRAILING,
        max_filings=2,
        trailing_10k=2,
        trailing_10q=2,
    )

    def _fake_list(**kwargs):
        base = FilingResolution(
            ticker="AAPL",
            cik="0000320193",
            accession="0000320193-24-000001",
            form_type="10-K",
            filed_at=date(2024, 11, 1),
            period_end=date(2024, 9, 28),
            edgar_filing_url="fixture://",
        )
        return [
            base,
            base.model_copy(update={"accession": "0000320193-24-000002", "form_type": "10-Q"}),
            base.model_copy(update={"accession": "0000320193-24-000003", "form_type": "10-Q"}),
            base.model_copy(update={"accession": "0000320193-24-000004", "form_type": "10-K"}),
        ]

    monkeypatch.setattr("ingestion.corpus.list_recent_filings", _fake_list)
    with pytest.raises(CorpusCapExceededError):
        resolve_corpus_members(defn)
