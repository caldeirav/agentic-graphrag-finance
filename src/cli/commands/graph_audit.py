"""Reachability audit CLI for published graph snapshots."""

from __future__ import annotations

from pathlib import Path

import typer

from graph.reachability import audit_snapshot_reachability, save_reachability_report
from graph.registry import load_index
from graph.store import load_snapshot


def graph_audit(
    ticker: str = typer.Option(..., "--ticker", help="Issuer ticker"),
    snapshot_id: str | None = typer.Option(None, "--snapshot-id", help="Snapshot UUID"),
    graphs_dir: Path = typer.Option(Path("data/graphs"), "--graphs-dir"),
) -> None:
    """Run structural reachability audit and write ``.reachability.json``."""
    issuer = ticker.upper()
    sid = snapshot_id
    if not sid:
        index = load_index(issuer, graphs_dir)
        sid = index.latest_snapshot_id
    if not sid:
        typer.echo(f"No snapshot found for {issuer}", err=True)
        raise typer.Exit(1)

    snapshot = load_snapshot(issuer, sid, graphs_dir)
    report = audit_snapshot_reachability(snapshot)
    path = save_reachability_report(report, graphs_dir)
    typer.echo(f"Reachability report: {path}")
    typer.echo(f"pass_rate={report.pass_rate:.2%} audit_ready={report.audit_ready}")

    if not report.audit_ready:
        raise typer.Exit(2)
