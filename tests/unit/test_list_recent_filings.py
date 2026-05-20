"""list_recent_filings in fixture mode."""

from ingestion.edgar_client import list_recent_filings


def test_list_fixture_filings_dedupes():
    filings = list_recent_filings(ticker="AAPL", form_types=["10-K", "10-Q"], max_per_form=4)
    assert len(filings) >= 2
    forms = {f.form_type for f in filings}
    assert "10-K" in forms
    assert "10-Q" in forms
    accessions = {f.accession for f in filings}
    assert len(accessions) == len(filings)
