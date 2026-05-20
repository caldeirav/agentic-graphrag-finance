"""Unified agent-query CLI."""

import typer

import cli.bootstrap  # noqa: F401  # load .env first
from cli.commands.ask import ask
from cli.commands.graph_audit import graph_audit
from cli.commands.materialize import materialize
from cli.commands.mlflow_clean import mlflow_clean
from cli.commands.test import test_cmd

app = typer.Typer(
    name="agent-query",
    help="Live SEC disclosure fetch, graph build, and agentic Q&A",
    no_args_is_help=True,
)
app.command("ask")(ask)
app.command("materialize")(materialize)
app.command("graph-audit")(graph_audit)
app.command("test")(test_cmd)
app.command("mlflow-clean")(mlflow_clean)
