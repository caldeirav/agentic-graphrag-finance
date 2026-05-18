"""Unified agent-query CLI."""

import typer

from cli.commands.ask import ask
from cli.commands.test import test_cmd

app = typer.Typer(
    name="agent-query",
    help="Live SEC disclosure fetch, graph build, and agentic Q&A",
    no_args_is_help=True,
)
app.command("ask")(ask)
app.command("test")(test_cmd)
