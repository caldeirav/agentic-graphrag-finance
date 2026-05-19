import pytest

from ingestion.settings import ConfigurationError, require_edgar_user_agent


def test_missing_edgar_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    from ingestion import settings

    settings.get_settings.cache_clear()
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "")
    with pytest.raises(ConfigurationError, match="SEC_EDGAR_USER_AGENT"):
        require_edgar_user_agent()


def test_edgar_user_agent_accepted(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Test User test@example.com")
    from ingestion import settings

    settings.get_settings.cache_clear()
    assert require_edgar_user_agent() == "Test User test@example.com"
