from ingestion import fetch_filing


def test_cache_hit_on_second_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "test-mock")
    root = tmp_path / "downloads"
    monkeypatch.setenv("SEC_DOWNLOADS_ROOT", str(root))
    from ingestion import settings

    settings.get_settings.cache_clear()

    first = fetch_filing(ticker="AAPL", form_type="10-K")
    assert first.cache_hit is False

    second = fetch_filing(ticker="AAPL", form_type="10-K")
    assert second.cache_hit is True

    third = fetch_filing(ticker="AAPL", form_type="10-K", force_refresh=True)
    assert third.cache_hit is False
