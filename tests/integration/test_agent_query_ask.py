
from typer.testing import CliRunner

from cli.main import app


def test_agent_query_ask_mock(monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "test-mock")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    from ingestion import settings

    settings.get_settings.cache_clear()

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ask",
            "--ticker",
            "AAPL",
            "--query",
            "What is revenue?",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "answer" in result.stdout.lower() or "text" in result.stdout
