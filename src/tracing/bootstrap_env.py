"""Load .env and configure MLflow before any CLI or pipeline work."""

from __future__ import annotations

import logging
import os
import warnings

from dotenv import load_dotenv

from tracing.mlflow_langgraph import configure_mlflow


def bootstrap_env() -> None:
    load_dotenv()
    os.environ.setdefault("LITELLM_LOG", "ERROR")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    logging.getLogger("litellm").setLevel(logging.ERROR)
    warnings.filterwarnings(
        "ignore",
        message=".*export_to_dataframe.*without `doc` argument is deprecated.*",
        category=DeprecationWarning,
    )
    configure_mlflow()
