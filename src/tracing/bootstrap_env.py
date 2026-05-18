"""Load .env and configure MLflow before any CLI or pipeline work."""

from dotenv import load_dotenv

from tracing.mlflow_langgraph import configure_mlflow


def bootstrap_env() -> None:
    load_dotenv()
    configure_mlflow()
