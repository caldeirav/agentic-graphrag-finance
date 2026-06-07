"""CLI tests for repro judge-batch flags."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from cli.main import app


def test_judge_batch_help_lists_input_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["repro", "judge-batch", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.stdout


def test_judge_batch_accepts_input_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    repro_dir = tmp_path / "repro-run"
    repro_dir.mkdir()
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("release_tag: test\n", encoding="utf-8")
    rel = MagicMock(
        release_tag="test",
        eval_split="dev",
        custom_judge_bundle_path="tests/fixtures/custom_judge",
        custom_judge_version="v2",
    )
    monkeypatch.setattr("cli.commands.repro.load_release_manifest", lambda _p: rel)
    mock_batch = MagicMock(return_value={"judged": 0, "skipped": 0, "failed": 0})
    monkeypatch.setattr("cli.commands.repro.run_judge_batch", mock_batch)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "repro",
            "judge-batch",
            "--input",
            str(repro_dir),
            "--manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.stdout
    mock_batch.assert_called_once()
    assert mock_batch.call_args.args[0] == repro_dir


def test_judge_batch_accepts_output_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OFFLINE_BENCHMARK", "1")
    repro_dir = tmp_path / "repro-run"
    repro_dir.mkdir()
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("release_tag: test\n", encoding="utf-8")
    rel = MagicMock(
        release_tag="test",
        eval_split="dev",
        custom_judge_bundle_path="tests/fixtures/custom_judge",
        custom_judge_version="v2",
    )
    monkeypatch.setattr("cli.commands.repro.load_release_manifest", lambda _p: rel)
    mock_batch = MagicMock(return_value={"judged": 0, "skipped": 0, "failed": 0})
    monkeypatch.setattr("cli.commands.repro.run_judge_batch", mock_batch)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "repro",
            "judge-batch",
            "--output",
            str(repro_dir),
            "--manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert mock_batch.call_args.args[0] == repro_dir
