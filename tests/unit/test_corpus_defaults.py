"""Default multi-year corpus definition and member resolution."""

from datetime import date

from ingestion.corpus import (
    default_corpus_definition,
    resolve_corpus_members,
    trailing_counts_from_config,
)
from models.corpus import CorpusDefinitionMode
from models.ingestion import FilingResolution


def test_trailing_years_derives_k_and_q_counts():
    assert trailing_counts_from_config({"trailing_years": 2}) == (2, 8)
    assert trailing_counts_from_config({"trailing_10k": 1, "trailing_10q": 4}) == (1, 4)


def test_default_corpus_definition_two_years():
    defn = default_corpus_definition("AAPL", ticker="AAPL")
    assert defn.trailing_10k == 2
    assert defn.trailing_10q == 8
    assert defn.max_filings >= 10


def test_resolve_default_trailing_two_10k(monkeypatch):
    defn = default_corpus_definition("AAPL", ticker="AAPL")

    def _fake_list(**kwargs):
        assert kwargs.get("max_per_form", 0) >= 8
        base = FilingResolution(
            ticker="AAPL",
            cik="0000320193",
            accession="0000320193-25-000079",
            form_type="10-K",
            filed_at=date(2025, 11, 1),
            period_end=date(2025, 9, 27),
            edgar_filing_url="fixture://",
        )
        return [
            base,
            base.model_copy(
                update={
                    "accession": "0000320193-24-000123",
                    "filed_at": date(2024, 11, 1),
                    "period_end": date(2024, 9, 28),
                }
            ),
            base.model_copy(
                update={
                    "accession": "0000320193-25-000001",
                    "form_type": "10-Q",
                    "period_end": date(2025, 6, 28),
                }
            ),
            base.model_copy(
                update={
                    "accession": "0000320193-25-000002",
                    "form_type": "10-Q",
                    "period_end": date(2025, 3, 29),
                }
            ),
        ]

    monkeypatch.setattr("ingestion.corpus.list_recent_filings", _fake_list)
    resolutions = resolve_corpus_members(defn)
    tens_k = [r for r in resolutions if r.form_type == "10-K"]
    assert len(tens_k) == 2
    assert defn.mode == CorpusDefinitionMode.DEFAULT_TRAILING
