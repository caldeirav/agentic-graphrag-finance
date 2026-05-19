"""Purge MLflow tracking data."""

from __future__ import annotations

import typer

from tracing.cleanup import cleanup_mlflow_tracking


def mlflow_clean(
    keep_dirs: bool = typer.Option(
        False,
        "--keep-dirs",
        help="Do not delete legacy mlruns/ or broken ${MLFLOW*} folders",
    ),
) -> None:
    stats = cleanup_mlflow_tracking(delete_legacy_dirs=not keep_dirs)
    typer.echo(
        f"MLflow cleanup ({stats['tracking_uri']}): "
        f"deleted {stats['deleted_runs']} run(s), removed {stats['removed_dirs']} legacy dir(s)."
    )
