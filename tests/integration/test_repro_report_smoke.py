"""Integration smoke test for repro report generation (014)."""

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_SMOKE = REPO_ROOT / "reports" / "repro-live-smoke"


def test_render_html_from_live_smoke_or_fixture(tmp_path: Path) -> None:
    input_dir = LIVE_SMOKE if LIVE_SMOKE.is_dir() else None
    if input_dir is None:
        from fixtures.repro_report_bundle import write_minimal_repro_bundle

        input_dir = write_minimal_repro_bundle(tmp_path)

    out = input_dir / "report-smoke-test.html"
    result = runner.invoke(
        app,
        ["repro", "report", "--input", str(input_dir), "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "Run Summary" in html
    assert "headline" in html.lower() or "Paper tables" in html
    assert "http" not in html.lower() or "mlflow" in html.lower()  # no CDN scripts
