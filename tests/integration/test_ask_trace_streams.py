import json

from typer.testing import CliRunner

from cli.main import app


def test_json_stdout_has_no_trace_keys(monkeypatch) -> None:
    monkeypatch.setenv("USE_FIXTURE_INGESTION", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    from ingestion import settings

    settings.get_settings.cache_clear()

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["ask", "--ticker", "AAPL", "--query", "What is revenue?", "--json", "--trace", "quiet"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "trace_events" not in payload
    assert "answer_text" in payload or "status" in payload


def test_trace_normal_writes_stage_headers_to_stderr(monkeypatch) -> None:
    monkeypatch.setenv("USE_FIXTURE_INGESTION", "1")
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
            "What are principal risk factors?",
            "--trace",
            "normal",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    err = result.stderr.lower()
    assert "macro" in err or "intent" in err
    assert "micro" in err or "synthesize" in err


def test_trace_json_emits_jsonl_on_stderr(monkeypatch) -> None:
    monkeypatch.setenv("USE_FIXTURE_INGESTION", "1")
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
            "--trace",
            "quiet",
            "--trace-json",
        ],
    )
    assert result.exit_code == 0, result.stderr
    lines = [ln for ln in result.stderr.splitlines() if ln.strip().startswith("{")]
    assert len(lines) >= 3
    json.loads(lines[0])
