"""Load .env and configure MLflow before agent-query imports."""

from tracing.bootstrap_env import bootstrap_env

bootstrap_env()
