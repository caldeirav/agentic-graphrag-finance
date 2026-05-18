import pytest

from ingestion.sec_client import ResolutionError, resolve_identifier, resolve_ticker


def test_resolve_ticker_aapl():
    assert resolve_ticker("AAPL") == "0000320193"


def test_unknown_ticker_mock_mode():
    with pytest.raises(ResolutionError, match="Unknown ticker"):
        resolve_identifier(ticker="ZZZZUNKNOWN", form_type="10-K")
