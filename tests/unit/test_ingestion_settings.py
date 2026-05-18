
import pytest

from ingestion.settings import ConfigurationError, require_sec_api_key


def test_missing_sec_api_key(monkeypatch):
    monkeypatch.delenv("SEC_API_KEY", raising=False)
    from ingestion import settings

    settings.get_settings.cache_clear()
    monkeypatch.setenv("SEC_API_KEY", "")
    settings.get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="SEC_API_KEY"):
        require_sec_api_key()


def test_mock_key_accepted(monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "test-mock")
    from ingestion import settings

    settings.get_settings.cache_clear()
    assert require_sec_api_key() == "test-mock"
