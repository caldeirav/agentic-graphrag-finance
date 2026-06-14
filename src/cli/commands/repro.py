"""agent-query repro — research reproduction kit (012/013)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from evaluation.reproduction.defer_config import resolve_defer_config
from evaluation.reproduction.export import export_tables_from_disk, write_paper_tables
from evaluation.reproduction.judge_batch import run_judge_batch
from evaluation.reproduction.manifest import load_expected_checksums, load_release_manifest, resolve_release_manifest_path
from evaluation.reproduction.relevance import materialize_relevance_labels
from evaluation.reproduction.report_errors import ReportInputError, ReportRenderError
from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_models import PaperTableId
from evaluation.reproduction.report_render import render_html_report, render_latex_only
from evaluation.reproduction.runner import ReproRunner
from evaluation.reproduction.verify_tables import verify_tables

app = typer.Typer(
    name="repro",
    help="Research reproduction workflows for paper benchmark tables",
    no_args_is_help=True,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_item_ids_file(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(i) for i in payload]
    ids = payload.get("item_ids")
    if not isinstance(ids, list):
        raise typer.BadParameter(f"{path} must contain item_ids[] or a JSON list")
    return [str(i) for i in ids]


def _manifest_path(manifest: Path | None, release: str | None) -> Path:
    if manifest is not None and release:
        raise typer.BadParameter("Use either --manifest or --release, not both")
    if release:
        return resolve_release_manifest_path(release, repo_root=REPO_ROOT)
    if manifest is None:
        raise typer.BadParameter("Provide --manifest or --release")
    return manifest


def _require_offline() -> None:
    if os.environ.get("OFFLINE_BENCHMARK", "").strip() not in {"1", "true", "yes"}:
        raise typer.BadParameter("Set OFFLINE_BENCHMARK=1 for reproduction commands")


def _runner(manifest: Path, *, defer_judge: bool | None = None) -> ReproRunner:
    defer = resolve_defer_config(cli_defer=defer_judge) if defer_judge is not None else None
    return ReproRunner(
        manifest,
        repo_root=REPO_ROOT,
        defer_config=defer,
    )


@app.command("verify-corpus")
def verify_corpus(
    manifest: Path = typer.Option(..., "--manifest", help="Release manifest YAML"),
) -> None:
    """Verify bundled corpus hashes and registry preflight."""
    _require_offline()
    runner = _runner(manifest)
    runner.verify_corpus()
    typer.echo("Registry preflight passed (split header loaded, no eval items executed).")
    typer.echo("Corpus and bundle pins verified.")


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
    item_ids_file: Path | None = typer.Option(None, "--item-ids-file"),
    output: Path = typer.Option(Path("reports/repro-run"), "--output"),
    defer_judge: bool = typer.Option(False, "--defer-judge"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
) -> None:
    """Run one or more system variants."""
    _require_offline()
    runner = _runner(manifest, defer_judge=defer_judge)
    rel = runner.manifest
    from evaluation.reproduction.manifest import resolve_variant_configs

    item_ids = _load_item_ids_file(item_ids_file) if item_ids_file else None
    selected = [v.strip() for v in variants.split(",") if v.strip()] if variants else rel.variant_ids
    configs = [c for c in resolve_variant_configs(rel) if c.variant_id in selected]
    output.mkdir(parents=True, exist_ok=True)
    repro = runner.load_checkpoint(output) if resume else None
    for cfg in configs:
        typer.echo(f"Running variant {cfg.variant_id}...")
        runner.run_variant(cfg, max_items=max_items, item_ids=item_ids, output_dir=output, repro=repro)
    typer.echo(f"Variant runs written to {output}")


@app.command("judge-batch")
def judge_batch_cmd(
    input_dir: Annotated[
        Path,
        typer.Option(
            ...,
            "--input",
            "--output",
            help="Repro output directory (reports/repro-{tag})",
        ),
    ],
    manifest: Annotated[Path, typer.Option(..., "--manifest")],
    variant: str = typer.Option("", "--variant", help="Optional variant id"),
    concurrency: int = typer.Option(2, "--concurrency"),
    max_items: int | None = typer.Option(None, "--max-items"),
    force_rescore: bool = typer.Option(False, "--force-rescore", help="Re-judge all items"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-item progress lines"),
) -> None:
    """Run deferred judge batch on pending items in results.json."""
    _require_offline()
    rel = load_release_manifest(manifest)
    bundle = REPO_ROOT / rel.custom_judge_bundle_path

    def _progress(msg: str) -> None:
        if quiet and " item=" in msg:
            return
        typer.echo(msg)

    typer.echo(
        f"Judge batch: input={input_dir} manifest={manifest.name} "
        f"release={rel.release_tag} split={rel.eval_split}"
    )
    stats = run_judge_batch(
        input_dir,
        bundle_root=bundle,
        split=rel.eval_split,
        custom_judge_version=rel.custom_judge_version,
        concurrency=concurrency,
        max_items=max_items,
        force_rescore=force_rescore,
        variant_id=variant or None,
        progress=_progress,
    )
    typer.echo(f"Judge batch summary: {stats}")


@app.command("export-tables")
def export_tables(
    manifest: Path = typer.Option(..., "--manifest"),
    input_dir: Path = typer.Option(..., "--input"),
    allow_pending: bool = typer.Option(False, "--allow-pending-export"),
) -> None:
    """Aggregate variant result JSON into paper tables from checkpoints."""
    rel = load_release_manifest(manifest)
    if not allow_pending:
        import json

        from models.evaluation import BenchmarkResult

        for variant_dir in input_dir.iterdir():
            path = variant_dir / "results.json"
            if not path.is_file():
                continue
            rows = [BenchmarkResult.model_validate(r) for r in json.loads(path.read_text())]
            if any(r.judge_status == "pending" for r in rows):
                raise typer.BadParameter(
                    f"Variant {variant_dir.name} has pending judge items; "
                    "run judge-batch or pass --allow-pending-export"
                )
    export = export_tables_from_disk(
        input_dir,
        release_tag=rel.release_tag,
        manifest=rel,
        repo_root=REPO_ROOT,
    )
    write_paper_tables(export, input_dir)
    typer.echo(f"Tables written to {input_dir / 'tables'}")


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
    manifest: Path | None = typer.Option(None, "--manifest"),
    release: str | None = typer.Option(None, "--release", help="Release tag e.g. paper-v2.0"),
    output: Path = typer.Option(None, "--output"),
    max_items: int | None = typer.Option(None, "--max-items"),
    item_ids_file: Path | None = typer.Option(
        None,
        "--item-ids-file",
        help="JSON file with item_ids[] for subset repro",
    ),
    skip_relevance: bool = typer.Option(False, "--skip-relevance"),
    strict_git: bool = typer.Option(
        False,
        "--strict-git",
        help="Fail when HEAD != manifest git_sha (opt-in; default verifies data hashes only)",
    ),
    defer_judge: bool = typer.Option(False, "--defer-judge"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    judge_only: bool = typer.Option(False, "--judge-only"),
    export_only: bool = typer.Option(False, "--export-only"),
    allow_pending_export: bool = typer.Option(False, "--allow-pending-export"),
) -> None:
    """Full reproduction: verify corpus, relevance gate, all variants, export tables."""
    _require_offline()
    if allow_pending_export:
        os.environ["REPRO_ALLOW_PENDING_EXPORT"] = "1"
    rel = load_release_manifest(_manifest_path(manifest, release))
    out = output or Path(f"reports/repro-{rel.release_tag}")
    item_ids = _load_item_ids_file(item_ids_file) if item_ids_file else None
    runner = _runner(_manifest_path(manifest, release), defer_judge=defer_judge)
    repro = runner.run_all(
        output_dir=out,
        max_items=max_items,
        item_ids=item_ids,
        skip_relevance=skip_relevance,
        strict_git=strict_git,
        resume=resume,
        export_only=export_only,
        judge_only=judge_only,
        cli_defer=defer_judge,
    )
    typer.echo(f"Reproduction complete: {repro.status} -> {out}")


DEFAULT_MAX_ITEM_ROWS = 500
DEFAULT_DELTA_THRESHOLD = 0.10
_TABLE_ID_MAP = {t.value: t for t in PaperTableId}


@app.command("report")
def report_cmd(
    input_dir: Path = typer.Option(..., "--input", help="Existing repro output directory"),
    output: Path | None = typer.Option(None, "--output", help="HTML output path"),
    format: str = typer.Option("html", "--format", help="html or latex-only"),
    table: list[str] = typer.Option([], "--table", help="Limit tables (repeatable)"),
    max_item_rows: int = typer.Option(DEFAULT_MAX_ITEM_ROWS, "--max-item-rows"),
    manifest: Path | None = typer.Option(None, "--manifest", help="Release manifest path"),
    delta_threshold: float = typer.Option(DEFAULT_DELTA_THRESHOLD, "--delta-threshold"),
) -> None:
    """Generate static HTML report or LaTeX table snippets from repro artifacts."""
    try:
        bundle = load_repro_report_bundle(input_dir, manifest_path=manifest)
    except ReportInputError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    table_ids: list[PaperTableId] | None = None
    if table:
        unknown = [t for t in table if t not in _TABLE_ID_MAP]
        if unknown:
            typer.echo(f"Unknown --table value(s): {', '.join(unknown)}", err=True)
            raise typer.Exit(code=2)
        table_ids = [_TABLE_ID_MAP[t] for t in table]

    if format == "latex-only":
        typer.echo(render_latex_only(bundle, table_ids=table_ids), nl=False)
        return

    if format != "html":
        typer.echo(f"Unsupported --format {format!r}; use html or latex-only", err=True)
        raise typer.Exit(code=2)

    out_path = output or (input_dir / "report.html")
    try:
        artifact = render_html_report(
            bundle,
            out_path,
            table_ids=table_ids,
            max_item_rows=max_item_rows,
            delta_threshold=delta_threshold,
        )
    except ReportRenderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    typer.echo(f"Report written to {artifact.html_path}")


@app.command("smoke-run")
def smoke_run_cmd(
    output: Path = typer.Option(
        Path("reports/repro-paper-v2.0-smoke"),
        "--output",
        help="Smoke repro output directory",
    ),
    manifest: Path = typer.Option(
        REPO_ROOT / "releases/paper-v2.0-smoke/manifest.yaml",
        "--manifest",
    ),
    subset: str = typer.Option(
        "full",
        "--subset",
        help="Item list: full (50 stratified) or finagent (all finagentbench dev items)",
    ),
    defer_judge: bool = typer.Option(True, "--defer-judge/--no-defer-judge"),
    resume: bool = typer.Option(False, "--resume/--no-resume"),
    judge_after: bool = typer.Option(True, "--judge-after/--no-judge-after"),
) -> None:
    """Run graph-full on a smoke subset (agent iteration loop)."""
    _require_offline()
    from evaluation.reproduction.smoke_gate import (
        DEFAULT_VARIANT,
        build_finagent_smoke_ids,
        load_smoke_item_ids,
        resolve_smoke_item_ids_path,
        write_smoke_item_ids_file,
    )

    rel = load_release_manifest(manifest)
    bundle = REPO_ROOT / rel.custom_judge_bundle_path
    if subset == "finagent":
        rel_path = resolve_smoke_item_ids_path("finagent")
        finagent_path = bundle / rel_path
        if not finagent_path.is_file():
            ids = build_finagent_smoke_ids(bundle, split=rel.eval_split)
            write_smoke_item_ids_file(
                bundle,
                ids,
                rel_path,
                label="finagentbench dev smoke",
            )
            typer.echo(f"Wrote {len(ids)} finagent ids to {finagent_path}")
    else:
        rel_path = rel.smoke_item_ids_path or resolve_smoke_item_ids_path(None)
    item_ids = load_smoke_item_ids(bundle, rel_path)
    typer.echo(
        f"Smoke run: {len(item_ids)} items, subset={subset}, variant={DEFAULT_VARIANT}, output={output}"
    )
    runner = _runner(manifest, defer_judge=defer_judge)
    runner.run_all(
        output_dir=output,
        item_ids=item_ids,
        skip_relevance=True,
        resume=resume,
        cli_defer=defer_judge,
    )
    if judge_after:
        typer.echo("Running judge batch on smoke subset...")
        runner.run_judge_batch_phase(output, variant_id=DEFAULT_VARIANT)
    typer.echo(f"Smoke agent run complete: {output}")


@app.command("smoke-materialize")
def smoke_materialize_cmd(
    manifest: Path = typer.Option(
        REPO_ROOT / "releases/paper-v2.0-smoke/manifest.yaml",
        "--manifest",
    ),
    subset: str = typer.Option("full", "--subset", help="full or finagent item list file"),
) -> None:
    """Regenerate smoke item list files and rematerialize divestiture-aware relevance labels."""
    _require_offline()
    from evaluation.reproduction.relevance import materialize_relevance_labels
    from evaluation.reproduction.smoke_gate import (
        build_finagent_smoke_ids,
        build_stratified_smoke_ids,
        resolve_smoke_item_ids_path,
        write_smoke_item_ids_file,
    )

    rel = load_release_manifest(manifest)
    bundle = REPO_ROOT / rel.custom_judge_bundle_path
    if subset == "finagent":
        ids = build_finagent_smoke_ids(bundle, split=rel.eval_split)
        path = write_smoke_item_ids_file(
            bundle,
            ids,
            resolve_smoke_item_ids_path("finagent"),
            label="finagentbench dev smoke",
        )
        typer.echo(f"Wrote {len(ids)} finagent ids to {path}")
    else:
        ids = build_stratified_smoke_ids(bundle, split=rel.eval_split, count=50)
        path = write_smoke_item_ids_file(
            bundle,
            ids,
            resolve_smoke_item_ids_path(None),
            label="stratified 50-item smoke",
        )
        typer.echo(f"Wrote {len(ids)} stratified smoke ids to {path}")
    typer.echo("Rematerializing relevance labels (divestiture chunk merge)...")
    sidecar = materialize_relevance_labels(bundle, split=rel.eval_split)
    typer.echo(
        f"Relevance: coverage={sidecar.coverage_rate:.3f} hash={sidecar.labels_hash[:20]}..."
    )


@app.command("smoke-gate")
def smoke_gate_cmd(
    input_dir: Path = typer.Option(..., "--input", help="Repro output with graph-full/results.json"),
    manifest: Path = typer.Option(
        REPO_ROOT / "releases/paper-v2.0-smoke/manifest.yaml",
        "--manifest",
    ),
    subset: str = typer.Option(
        "full",
        "--subset",
        help="Item list: full (50 stratified) or finagent (finagentbench dev items)",
    ),
    variant: str = typer.Option("graph-full", "--variant"),
    fail: bool = typer.Option(True, "--fail/--no-fail", help="Exit 1 when gate fails"),
) -> None:
    """Evaluate smoke gate thresholds on an existing graph-full results.json."""
    from evaluation.reproduction.smoke_gate import (
        SmokeGateThresholds,
        evaluate_smoke_gate,
        format_smoke_report,
        load_smoke_item_ids,
        profile_map_from_bundle,
        resolve_smoke_item_ids_path,
    )

    rel = load_release_manifest(manifest)
    bundle = REPO_ROOT / rel.custom_judge_bundle_path
    if subset != "full":
        rel_path = resolve_smoke_item_ids_path(subset)
    else:
        rel_path = rel.smoke_item_ids_path or resolve_smoke_item_ids_path(None)
    item_ids = load_smoke_item_ids(bundle, rel_path)
    thresholds = SmokeGateThresholds.from_mapping(rel.smoke_gate_thresholds or None)
    results_path = input_dir / variant / "results.json"
    profiles = profile_map_from_bundle(bundle, rel.eval_split)
    result = evaluate_smoke_gate(
        results_path,
        item_ids,
        thresholds=thresholds,
        profile_by_item=profiles,
    )
    typer.echo(format_smoke_report(result, item_ids=item_ids))
    if fail and not result.ok:
        raise typer.Exit(code=1)
