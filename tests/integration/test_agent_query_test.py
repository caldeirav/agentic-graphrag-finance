from typer.testing import CliRunner

from cli.main import app


def test_agent_query_test_mock(monkeypatch):
    monkeypatch.setenv("USE_FIXTURE_INGESTION", "1")
    from ingestion import settings

    settings.get_settings.cache_clear()

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["test", "--ticker", "AAPL", "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
