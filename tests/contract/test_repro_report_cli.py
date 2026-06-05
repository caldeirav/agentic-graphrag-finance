"""Contract tests for repro report CLI (014)."""

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app
from fixtures.repro_report_bundle import write_minimal_repro_bundle

runner = CliRunner()


def test_latex_only_headline_stdout(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    result = runner.invoke(
        app,
        ["repro", "report", "--input", str(tmp_path), "--format", "latex-only", "--table", "headline"],
    )
    assert result.exit_code == 0
    assert "\\begin{table}" in result.stdout
    assert "release_tag: paper-smoke" in result.stdout


def test_missing_input_exit_code_2(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    result = runner.invoke(app, ["repro", "report", "--input", str(missing)])
    assert result.exit_code == 2


def test_invalid_csv_exit_code_2(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path, bad_csv_header=True)
    result = runner.invoke(app, ["repro", "report", "--input", str(tmp_path)])
    assert result.exit_code == 2
    assert "header mismatch" in result.stderr or "header mismatch" in result.stdout


def test_html_report_written(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    out = tmp_path / "custom.html"
    result = runner.invoke(
        app,
        ["repro", "report", "--input", str(tmp_path), "--output", str(out)],
    )
    assert result.exit_code == 0
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "Run Summary" in content
    assert "Paper tables" in content
