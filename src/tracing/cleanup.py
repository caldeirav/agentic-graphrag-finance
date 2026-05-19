"""Remove stale MLflow runs and legacy file-store artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path

from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

from tracing.mlflow_langgraph import configure_mlflow, load_mlflow_config


def cleanup_mlflow_tracking(*, delete_legacy_dirs: bool = True) -> dict[str, int | str]:
    """Delete all runs in the configured experiment and optional legacy ``mlruns/`` dirs."""
    load_dotenv()
    uri = configure_mlflow()
    cfg = load_mlflow_config()
    experiment_name = cfg.get("experiment_name", "sec-disclosure-rag")
    client = MlflowClient(tracking_uri=uri)

    deleted_runs = 0
    reset_sqlite = uri.startswith("sqlite:///") and delete_legacy_dirs
    if reset_sqlite:
        db_file = Path(uri.removeprefix("sqlite:///"))
        for path in (db_file, Path(f"{db_file}-journal"), Path(f"{db_file}-wal"), Path(f"{db_file}-shm")):
            if path.is_file():
                path.unlink()
        uri = configure_mlflow()
        client = MlflowClient(tracking_uri=uri)
    else:
        exp = client.get_experiment_by_name(experiment_name)
        if exp is not None:
            runs = client.search_runs(experiment_ids=[exp.experiment_id])
            for run in runs:
                client.delete_run(run.info.run_id)
                deleted_runs += 1

    removed_dirs = 0
    if delete_legacy_dirs:
        cwd = Path.cwd()
        for name in ("mlruns",):
            path = cwd / name
            if path.is_dir():
                shutil.rmtree(path)
                removed_dirs += 1
        for path in cwd.iterdir():
            if path.is_dir() and path.name.startswith("${MLFLOW"):
                shutil.rmtree(path)
                removed_dirs += 1

    return {"deleted_runs": deleted_runs, "removed_dirs": removed_dirs, "tracking_uri": uri}
