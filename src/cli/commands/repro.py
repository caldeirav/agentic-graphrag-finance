"""agent-query repro — research reproduction kit (012)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from evaluation.reproduction.manifest import load_expected_checksums, load_release_manifest
from evaluation.reproduction.relevance import materialize_relevance_labels
from evaluation.reproduction.runner import ReproRunner
from evaluation.reproduction.verify_tables import verify_tables

app = typer.Typer(
    name="repro",
    help="Research reproduction workflows for paper benchmark tables",
    no_args_is_help=True,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _require_offline() -> None:
    if os.environ.get("OFFLINE_BENCHMARK", "").strip() not in {"1", "true", "yes"}:
        raise typer.BadParameter("Set OFFLINE_BENCHMARK=1 for reproduction commands")


def _runner(manifest: Path) -> ReproRunner:
    return ReproRunner(manifest, repo_root=REPO_ROOT)


@app.command("verify-corpus")
def verify_corpus(
    manifest: Path = typer.Option(..., "--manifest", help="Release manifest YAML"),
) -> None:
    """Verify bundled corpus hashes and registry preflight."""
    _require_offline()
    runner = _runner(manifest)
    runner.verify_corpus()
    typer.echo("Registry preflight passed (split header loaded, no eval items executed).")
    typer.echo("Corpus verification passed.")


@app.command("materialize-relevance")
def materialize_relevance(
    manifest: Path = typer.Option(..., "--manifest"),
) -> None:
    """Derive graph-grounded relevant_chunk_ids for the bundle."""
    rel_manifest = load_release_manifest(manifest)
    bundle = REPO_ROOT / rel_manifest.custom_judge_bundle_path
    sidecar = materialize_relevance_labels(bundle, split=rel_manifest.eval_split)
    typer.echo(f"Relevance materialized: coverage={sidecar.coverage_rate:.2%} hash={sidecar.labels_hash}")


@app.command("run")
def run_variants(
    manifest: Path = typer.Option(..., "--manifest"),
    variants: str = typer.Option("", "--variants", help="Comma-separated variant ids"),
    max_items: int | None = typer.Option(None, "--max-items"),
    output: Path = typer.Option(Path("reports/repro-run"), "--output"),
) -> None:
    """Run one or more system variants."""
    _require_offline()
    runner = _runner(manifest)
    rel = runner.manifest
    from evaluation.reproduction.manifest import resolve_variant_configs

    selected = [v.strip() for v in variants.split(",") if v.strip()] if variants else rel.variant_ids
    configs = [c for c in resolve_variant_configs(rel) if c.variant_id in selected]
    output.mkdir(parents=True, exist_ok=True)
    for cfg in configs:
        typer.echo(f"Running variant {cfg.variant_id}...")
        runner.run_variant(cfg, max_items=max_items, output_dir=output)
    typer.echo(f"Variant runs written to {output}")


@app.command("export-tables")
def export_tables(
    manifest: Path = typer.Option(..., "--manifest"),
    input_dir: Path = typer.Option(..., "--input"),
) -> None:
    """Aggregate variant result JSON into paper tables (requires prior run)."""
    typer.echo("Use repro run-all to export tables in one step; standalone export reads results.json")
    raise typer.Exit(code=0)


@app.command("verify-tables")
def verify_tables_cmd(
    manifest: Path = typer.Option(..., "--manifest"),
    input_dir: Path = typer.Option(..., "--input"),
) -> None:
    """Compare exported tables to release expected checksums."""
    rel = load_release_manifest(manifest)
    expected = load_expected_checksums(manifest, rel)
    result = verify_tables(rel, input_dir / "tables", expected)
    if not result.ok:
        raise typer.BadParameter(result.message)
    typer.echo(result.message)


@app.command("run-all")
def run_all(
    manifest: Path = typer.Option(..., "--manifest"),
    output: Path = typer.Option(None, "--output"),
    max_items: int | None = typer.Option(None, "--max-items"),
    skip_relevance: bool = typer.Option(False, "--skip-relevance"),
    strict_git: bool = typer.Option(False, "--strict-git"),
) -> None:
    """Full reproduction: verify corpus, relevance gate, all variants, export tables."""
    _require_offline()
    rel = load_release_manifest(manifest)
    out = output or Path(f"reports/repro-{rel.release_tag}")
    runner = _runner(manifest)
    repro = runner.run_all(
        output_dir=out,
        max_items=max_items,
        skip_relevance=skip_relevance,
        strict_git=strict_git or rel.release_tag == "paper-v1.0",
    )
    typer.echo(f"Reproduction complete: {repro.status} -> {out}")
