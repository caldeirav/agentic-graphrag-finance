"""agent-query benchmark-dataset — judge-generated custom evaluation dataset (011)."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import typer

from cli.benchmark_catalog import build_accession_catalog
from cli.benchmark_materialize import materialize_sampled_corpus
from cli.benchmark_trace import BenchmarkTraceReporter
from evaluation.generation.bundle import (
    apply_profile_balanced_dev_split,
    publish_draft,
    validate_bundle_feasibility,
    write_draft_manifest,
    write_scorability_report,
)
from evaluation.generation.publish_audit import write_audit_sample, write_publish_audit
from evaluation.generation.config_loader import load_allowlist, load_generation_config
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.judge_generator import PUBLISH_MIN_ACCEPTED, generate_items, write_items_jsonl
from evaluation.generation.sampler import (
    run_sampling,
    sampling_manifest_hash,
)
from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.bulk_regenerate import (
    regenerate_boilerplate_items,
    regenerate_items_from_file,
    write_bulk_regenerate_report,
)
from evaluation.generation.review.feedback import BOILERPLATE_REGEN_FEEDBACK
from evaluation.generation.review.csv_annotations import (
    _load_item_ids_file,
    build_annotation_sheet_rows,
    import_annotations_from_csv,
    list_boilerplate_comparison_items,
    write_annotation_sheet,
)
from evaluation.generation.review.overrides import apply_overrides, load_regenerated_item_ids
from evaluation.generation.review.quality_summary import build_quality_pass_summary, write_quality_pass_summary
from evaluation.generation.review.queue import build_review_queue, write_review_queue
from evaluation.generation.review.regenerate_item import regenerate_item
from evaluation.generation.review.review_pack import write_review_pack
from evaluation.generation.review._paths import resolve_draft_bundle
from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    DatasetManifest,
    FailureClass,
    ProposedOverrides,
    ReproContextSnapshot,
    SamplingManifest,
)

app = typer.Typer(
    name="benchmark-dataset",
    help="Generate, publish, and reproduce custom-judge evaluation datasets",
    no_args_is_help=True,
)

review_app = typer.Typer(
    name="review",
    help="Human-in-the-loop dataset quality review (018)",
    no_args_is_help=True,
)
app.add_typer(review_app, name="review")

CI_CONFIG_ID = "custom_judge_ci"
LIVE_CONFIG_ID = "custom_judge_live"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _review_progress(message: str) -> None:
    """Echo progress and flush so long Gemini calls show status immediately."""
    import sys

    typer.echo(message)
    sys.stdout.flush()


def _mock_judge_requested(*, mock_judge: bool) -> bool:
    return mock_judge or os.environ.get("USE_MOCK_JUDGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def enforce_mock_judge_policy(config_path: Path, *, mock_judge: bool) -> None:
    """Reject mock judge unless config_id is custom_judge_ci (FR-014)."""
    if not _mock_judge_requested(mock_judge=mock_judge):
        return
    try:
        config = load_generation_config(config_path, base=REPO_ROOT)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    if config.config_id != CI_CONFIG_ID:
        raise typer.BadParameter(
            "--mock-judge and USE_MOCK_JUDGE=1 are allowed only with "
            f"config_id={CI_CONFIG_ID!r}, got {config.config_id!r}"
        )


def _draft_dir(config_path: Path, run_id: str | None) -> Path:
    config = load_generation_config(config_path, base=REPO_ROOT)
    rid = run_id or str(uuid.uuid4())[:8]
    return Path(config.output.drafts_root) / rid


def _prefer_fixtures(config_id: str) -> bool:
    return config_id == CI_CONFIG_ID


def _phase_needs_accession_catalog(phase: str) -> bool:
    """Live EDGAR catalog is only required for sampling (not judge/materialize resume)."""
    return phase in {"sampling", "all"}


@app.command("generate")
def generate(
    config: Path = typer.Option(
        Path("configs/benchmarks/custom_judge_v1.yaml"),
        "--config",
        "-c",
        exists=True,
        readable=True,
    ),
    run_id: str | None = typer.Option(None, "--run-id", help="Draft run identifier"),
    mock_judge: bool = typer.Option(False, "--mock-judge", help="Use mock judge (CI config only)"),
    phase: str = typer.Option(
        "all",
        "--phase",
        help="Pipeline phase: sampling | materialize | judge | all",
    ),
    target_items: int | None = typer.Option(
        None,
        "--target-items",
        help="Override item count for judge phase (default: config governance.max_items)",
    ),
    bundle_version: str | None = typer.Option(
        None,
        "--bundle-version",
        help="Target bundle semver (e.g. 2.0.0 for v2 net-new generation)",
    ),
    trace: str | None = typer.Option(
        None,
        "--trace",
        help="Console trace verbosity: quiet, normal, verbose",
    ),
) -> None:
    """Generate draft dataset (sampling → materialize → judge)."""
    enforce_mock_judge_policy(config, mock_judge=mock_judge)
    if mock_judge:
        os.environ["USE_MOCK_JUDGE"] = "1"

    reporter = BenchmarkTraceReporter.from_cli(trace)
    cfg = load_generation_config(config, base=REPO_ROOT)
    allowlist = load_allowlist(cfg.allowlist_path, base=REPO_ROOT)
    draft = _draft_dir(config, run_id)
    draft.mkdir(parents=True, exist_ok=True)

    reporter.summary(
        "Benchmark dataset generate",
        [
            f"config={config}",
            f"config_id={cfg.config_id}",
            f"draft_dir={draft}",
            f"phase={phase}",
            f"edgar={'fixture' if os.environ.get('USE_FIXTURE_INGESTION', '').strip() in {'1', 'true', 'yes'} else 'live'}",
            f"mock_judge={_mock_judge_requested(mock_judge=mock_judge)}",
            f"target_items={target_items or cfg.governance.max_items}",
        ],
    )

    catalog = None
    if _phase_needs_accession_catalog(phase):
        catalog = build_accession_catalog(
            cfg,
            allowlist,
            repo_root=REPO_ROOT,
            prefer_fixtures=_prefer_fixtures(cfg.config_id),
        )

    if phase in {"sampling", "all"}:
        assert catalog is not None
        reporter.phase_start("sampling", f"issuers={cfg.issuer_sample_count} seed={cfg.random_seed}")
        manifest = run_sampling(config, draft, catalog, repo_root=REPO_ROOT)
        manifest_hash = sampling_manifest_hash(manifest)
        issuers = ", ".join(i.ticker for i in manifest.selected_issuers)
        reporter.phase_end("sampling", f"hash={manifest_hash[:20]}… issuers=[{issuers}]")
        if phase == "sampling":
            reporter.summary("Done", [f"draft={draft}", f"sampling_hash={manifest_hash}"])
            return

    sampling_path = draft / "sampling_manifest.json"
    if not sampling_path.is_file():
        raise typer.BadParameter("Missing sampling_manifest.json; run --phase sampling first")
    sampling = SamplingManifest.model_validate(json.loads(sampling_path.read_text()))

    if phase in {"materialize", "all"}:
        reporter.phase_start(
            "materialize",
            f"filings={sum(len(i.accessions) for i in sampling.selected_issuers)}",
        )
        bundle, mat_report = materialize_sampled_corpus(
            sampling,
            draft,
            run_id=draft.name,
        )
        reporter.phase_end(
            "materialize",
            f"snapshot_id={bundle.snapshot_id} failures={mat_report.rejections_by_reason}",
        )
        if phase == "materialize":
            reporter.summary("Done", [f"draft={draft}", f"snapshot_id={bundle.snapshot_id}"])
            return

    if phase in {"judge", "all"}:
        index_path = draft / "corpus" / "graph_node_index.json"
        if not index_path.is_file():
            raise typer.BadParameter("Missing corpus graph index; run --phase materialize first")
        bundle_path = draft / "corpus_bundle.json"
        if not bundle_path.is_file():
            raise typer.BadParameter("Missing corpus_bundle.json; run --phase materialize first")

        if not _mock_judge_requested(mock_judge=mock_judge):
            try:
                GeminiItemGenerator.require_api_key()
            except RuntimeError as exc:
                raise typer.BadParameter(str(exc)) from exc

        from models.benchmark_generation import CorpusBundle

        bundle = CorpusBundle.model_validate(json.loads(bundle_path.read_text(encoding="utf-8")))
        reporter.phase_start(
            "judge",
            f"target_items={target_items or cfg.governance.max_items} "
            f"model={cfg.generation_judge_version}",
        )
        accepted, report = generate_items(
            cfg,
            sampling,
            draft,
            repo_root=REPO_ROOT,
            target_count=target_items,
            tracer=reporter,
        )
        items_path = draft / "items" / "dev.jsonl"
        selection: dict[str, object] | None = None
        if cfg.bundle_schema_version.startswith("2"):
            pool_path = draft / "items" / "dev_pool.jsonl"
            write_items_jsonl(accepted, pool_path)
            selection = apply_profile_balanced_dev_split(
                draft,
                profile_quotas=cfg.profile_quotas,
                target_count=PUBLISH_MIN_ACCEPTED,
                seed=cfg.random_seed,
            )
            selected_counts = selection.get("selected_counts") or {}
            reporter.log(
                "dev_selection "
                f"{selection.get('selected_count')}/{selection.get('pool_count')} items → "
                + ", ".join(
                    f"{profile}={selected_counts.get(profile, 0)}"
                    for profile in cfg.profile_quotas
                )
            )
        else:
            write_items_jsonl(accepted, items_path)
        write_draft_manifest(
            draft_dir=draft,
            config=cfg,
            sampling=sampling,
            bundle=bundle,
            report=report,
            items_path=items_path,
            version=bundle_version or "0.0.0-draft",
        )
        items = [
            json.loads(line)
            for line in items_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        from models.benchmark_generation import GeneratedBenchmarkItem

        parsed_items = [GeneratedBenchmarkItem.model_validate(row) for row in items]
        write_scorability_report(draft, items_path)
        feasibility = validate_bundle_feasibility(draft, items_path)
        (draft / "feasibility_report.json").write_text(
            json.dumps(feasibility, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_audit_sample(draft, parsed_items, seed=cfg.random_seed)
        if int(feasibility.get("blocked_count", 0)) > 0:
            raise typer.Exit(code=1)
        if cfg.governance.multi_filing_min and int(feasibility.get("multi_filing_count", 0)) < cfg.governance.multi_filing_min:
            raise typer.Exit(code=1)
        if cfg.bundle_schema_version.startswith("2") and selection is not None:
            selected_counts = selection.get("selected_counts") or {}
            phase_detail = (
                f"dev_selected={selection.get('selected_count')} "
                f"from_pool={selection.get('pool_count')} "
                + " ".join(
                    f"{profile}={selected_counts.get(profile, 0)}"
                    for profile in cfg.profile_quotas
                )
            )
            summary_lines = [
                f"draft={draft}",
                f"dev_selected={selection.get('selected_count')} "
                f"(profile-balanced from pool of {selection.get('pool_count')})",
                "dev_profile_counts="
                + ", ".join(
                    f"{profile}={selected_counts.get(profile, 0)}"
                    for profile in cfg.profile_quotas
                ),
                f"pool_accepted={report.accepted_count}/{report.candidates_total} "
                f"(candidate validation yield {report.pass_rate:.1%}, indicative only)",
                f"judge_api_calls={report.judge_api_calls}",
                f"duration={report.duration_seconds:.1f}s",
                f"items={items_path}",
                f"pool={draft / 'items' / 'dev_pool.jsonl'}",
            ]
        else:
            phase_detail = (
                f"accepted={report.accepted_count} rejected={report.rejected_count} "
                f"pass_rate={report.pass_rate:.0%}"
            )
            summary_lines = [
                f"draft={draft}",
                f"accepted={report.accepted_count}/{report.candidates_total}",
                f"pass_rate={report.pass_rate:.1%}",
                f"judge_api_calls={report.judge_api_calls}",
                f"duration={report.duration_seconds:.1f}s",
                f"items={items_path}",
            ]
        reporter.phase_end("judge", phase_detail)
        reporter.summary("Generate complete", summary_lines)


@app.command("publish")
def publish(
    draft_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    version: str = typer.Option(..., "--version", help="Semver version to publish"),
    min_items: int = typer.Option(200, "--min-items"),
    skip_gates: bool = typer.Option(False, "--skip-gates", help="Skip item count/pass-rate gates"),
    publish_signoff: bool = typer.Option(False, "--publish-signoff", help="Required for v2 publish"),
    operator_id: str | None = typer.Option(None, "--operator-id", help="Operator id for audit record"),
) -> None:
    """Promote a draft bundle to a published version."""
    cfg = load_generation_config(draft_dir / "generation_config.yaml", base=REPO_ROOT)
    v2 = cfg.bundle_schema_version.startswith("2")
    if v2 and not publish_signoff and not skip_gates:
        raise typer.BadParameter("v2 publish requires --publish-signoff")
    if v2 and publish_signoff:
        sample_path = draft_dir / "publish_audit.sample.json"
        if not sample_path.is_file():
            raise typer.BadParameter("Missing publish_audit.sample.json in draft")
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        write_publish_audit(
            draft_dir,
            operator_id=operator_id or os.environ.get("USER", "operator"),
            audit_item_ids=list(sample.get("audit_sample_item_ids") or []),
        )
    dest = publish_draft(
        draft_dir,
        version=version,
        published_root=Path(cfg.output.published_root),
        min_items=1 if skip_gates else min_items,
        skip_gates=skip_gates,
        multi_filing_min=cfg.governance.multi_filing_min,
        require_publish_audit=v2 and publish_signoff and not skip_gates,
        profile_quotas=cfg.profile_quotas if v2 else None,
        selection_seed=cfg.random_seed,
    )
    published_manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((draft_dir / "generation_report.json").read_text(encoding="utf-8"))
    typer.echo(f"Published custom-judge v{version} -> {dest}")
    if cfg.bundle_schema_version.startswith("2"):
        profile_counts = published_manifest.get("profile_counts") or {}
        typer.echo(
            "Published dev split: "
            f"{published_manifest.get('item_count', 0)} items — "
            + ", ".join(f"{profile}={profile_counts.get(profile, 0)}" for profile in cfg.profile_quotas)
        )
        selection_path = dest / "dev_selection_report.json"
        if selection_path.is_file():
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            typer.echo(
                f"Selection pool={selection.get('pool_count')} "
                f"seed={selection.get('seed')}"
            )
        typer.echo(
            "Generation yield (indicative, not a publish gate): "
            f"pass_rate={report.get('pass_rate', 0):.1%} "
            f"({report.get('accepted_count', 0)} pool-accepted / "
            f"{report.get('candidates_total', 0)} candidates)"
        )


@app.command("reproduce")
def reproduce(
    version: str = typer.Option("0.0.0-draft", "--version", help="Published dataset version"),
    bundle_root: Path | None = typer.Option(None, "--bundle-root"),
) -> None:
    """Recompute items_hash and verify manifest integrity."""
    from evaluation.datasets.custom_judge import CustomJudgeDataset
    from evaluation.generation.bundle import items_hash

    ds = CustomJudgeDataset(version=version, bundle_root=bundle_root)
    manifest = ds.manifest()
    items_path = ds._root / "items" / "dev.jsonl"
    computed = items_hash(items_path)
    if computed != manifest.items_hash:
        raise typer.Exit(code=1)
    typer.echo(f"Reproduce OK: version={version} items_hash={computed}")


@app.command("repair-bundle")
def repair_bundle_cmd(
    bundle_root: Path = typer.Argument(
        ...,
        help="Published bundle root (e.g. data/benchmarks/custom-judge/v2.0.0)",
    ),
    split: str = typer.Option("dev", "--split"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    skip_relevance: bool = typer.Option(False, "--skip-relevance"),
    repair_version: str = typer.Option(
        "v2",
        "--repair-version",
        help="v2 remaps divestiture paths to MD&A/10-Q and suppresses path injection",
    ),
) -> None:
    """Repair corrupt section paths, normalize numeric GT, and rematerialize relevance."""
    from evaluation.generation.bundle_repair_v2 import repair_bundle

    report = repair_bundle(
        bundle_root.resolve(),
        split=split,
        dry_run=dry_run,
        rematerialize_relevance=not skip_relevance,
        repair_version=repair_version,
    )
    typer.echo(
        f"scanned={report.items_scanned} paths_repaired={report.paths_repaired} "
        f"v2_cohort={report.v2_cohort_repaired} injection_suppressed={report.injection_suppressed} "
        f"numeric_normalized={report.numeric_normalized} "
        f"index_paths_removed={report.index_paths_removed} "
        f"changed_items={len(report.item_ids_changed)}"
    )
    if report.item_ids_changed:
        typer.echo(f"changed: {', '.join(report.item_ids_changed[:20])}")
        if len(report.item_ids_changed) > 20:
            typer.echo(f"... and {len(report.item_ids_changed) - 20} more")


@app.command("extend")
def extend(
    parent_version: str = typer.Option(..., "--parent-version"),
    config: Path = typer.Option(
        Path("configs/benchmarks/custom_judge_v1.yaml"),
        "--config",
        "-c",
        exists=True,
        readable=True,
    ),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Extend a published dataset with additional items."""
    cfg = load_generation_config(config, base=REPO_ROOT)
    parent_root = Path(cfg.output.published_root) / f"v{parent_version}"
    draft = _draft_dir(config, run_id)
    draft.mkdir(parents=True, exist_ok=True)
    if parent_root.is_dir():
        for name in ("items", "corpus", "sampling_manifest.json", "generation_config.yaml"):
            src = parent_root / name
            dest = draft / name
            if src.is_file():
                shutil.copy2(src, dest)
            elif src.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
    parent_manifest = DatasetManifest.model_validate(
        json.loads((parent_root / "manifest.json").read_text(encoding="utf-8"))
    )
    draft_manifest_path = draft / "manifest.json"
    if draft_manifest_path.is_file():
        draft_data = json.loads(draft_manifest_path.read_text())
    else:
        draft_data = parent_manifest.model_dump(mode="json")
    draft_data["parent_version"] = parent_version
    draft_data["status"] = "draft"
    draft_manifest_path.write_text(json.dumps(draft_data, indent=2) + "\n")
    typer.echo(f"Extend draft prepared at {draft} from parent v{parent_version}")


@review_app.command("export-queue")
def review_export_queue(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    repro_input: Path | None = typer.Option(None, "--repro-input", exists=True, file_okay=False, dir_okay=True),
    variant: str = typer.Option("graph-full", "--variant"),
    output: Path = typer.Option(Path("review_queue"), "--output"),
    tier: int | None = typer.Option(None, "--tier"),
    exclude_annotated: str | None = typer.Option(None, "--exclude-annotated"),
    max_items: int | None = typer.Option(None, "--max-items"),
) -> None:
    """Export prioritized review queue from repro results and dev split."""
    if repro_input is None:
        typer.echo("Warning: --repro-input omitted; all items assigned tier 3", err=True)
    exclude = {exclude_annotated} if exclude_annotated else None
    entries = build_review_queue(
        draft,
        repro_input=repro_input,
        variant=variant,
        tier_filter=tier,
        exclude_failure_classes=exclude,
        max_items=max_items,
    )
    out_base = output if output.is_absolute() else draft / output
    json_path, csv_path = write_review_queue(
        draft,
        entries,
        out_base,
        repro_input=repro_input,
        variant=variant,
    )
    typer.echo(f"Review queue: {len(entries)} entries -> {json_path}, {csv_path}")


@review_app.command("export-sheet")
def review_export_sheet(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_ids_file: Path | None = typer.Option(None, "--item-ids-file", exists=True),
    queue_file: Path | None = typer.Option(
        None,
        "--queue-file",
        exists=True,
        help="review_queue.json from export-queue",
    ),
    repro_input: Path | None = typer.Option(None, "--repro-input", exists=True, file_okay=False, dir_okay=True),
    variant: str = typer.Option("graph-full", "--variant"),
    output: Path = typer.Option(Path("annotation_sheet.csv"), "--output"),
    max_items: int | None = typer.Option(None, "--max-items"),
    exclude_regenerated: bool = typer.Option(
        False,
        "--exclude-regenerated",
        help="Omit items already fixed via fix-boilerplate/regenerate-item",
    ),
) -> None:
    """Export annotatable CSV (context columns + empty reviewer fields)."""
    if item_ids_file is None and queue_file is None:
        raise typer.BadParameter("Provide --item-ids-file or --queue-file")
    if queue_file is not None:
        item_ids = _load_item_ids_file(queue_file)
    else:
        assert item_ids_file is not None
        item_ids = _load_item_ids_file(item_ids_file)
    excluded = 0
    if exclude_regenerated:
        regen_ids = load_regenerated_item_ids(draft)
        before = len(item_ids)
        item_ids = [item_id for item_id in item_ids if item_id not in regen_ids]
        excluded = before - len(item_ids)
    if max_items:
        item_ids = item_ids[:max_items]
    rows = build_annotation_sheet_rows(
        draft,
        item_ids,
        repro_input=repro_input,
        variant=variant,
    )
    out_path = output if output.is_absolute() else draft / output
    if out_path.is_file():
        typer.echo(
            f"Note: overwriting existing sheet at {out_path} "
            "(copy your filled CSV first if you need to keep prior edits)",
            err=True,
        )
    write_annotation_sheet(out_path, rows)
    boilerplate_yes = sum(1 for row in rows if row.get("is_boilerplate_comparison") == "yes")
    boilerplate_no = len(rows) - boilerplate_yes
    typer.echo(f"Annotation sheet ({len(rows)} rows) -> {out_path}")
    if exclude_regenerated and excluded:
        typer.echo(f"Excluded {excluded} already-regenerated item(s) (--exclude-regenerated)")
    typer.echo(
        f"Breakdown: is_boilerplate_comparison=yes {boilerplate_yes}, no {boilerplate_no} "
        f"(review rows with no; skip rows already fixed by fix-boilerplate)"
    )
    typer.echo(
        "Fill failure_class, corpus_spot_check, notes, proposed_answer/proposed_question, "
        "apply=yes — then run review import-csv"
    )


@review_app.command("import-csv")
def review_import_csv(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    csv: Path = typer.Option(..., "--csv", exists=True, readable=True),
    reviewer_id: str = typer.Option(..., "--reviewer-id"),
    apply: bool = typer.Option(False, "--apply", help="Apply overrides after import"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    skip_failed: bool = typer.Option(False, "--skip-failed"),
    force: bool = typer.Option(False, "--force", help="Allow agent_failure overrides on apply"),
) -> None:
    """Import reviewer annotations from CSV into annotations.jsonl."""
    result = import_annotations_from_csv(
        draft,
        csv,
        reviewer_id=reviewer_id,
        apply_after=apply,
        dry_run=dry_run,
        skip_failed=skip_failed,
        force_agent_failure=force,
    )
    typer.echo(
        f"CSV import: imported={result.imported} skipped={result.skipped} "
        f"dry_run={dry_run} apply={apply}"
    )
    if result.fixed_items_path is not None:
        typer.echo(f"fixed_items.json refreshed -> {result.fixed_items_path}")
    if result.errors:
        for err in result.errors[:10]:
            typer.echo(f"  error: {err}", err=True)
        if len(result.errors) > 10:
            typer.echo(f"  ... and {len(result.errors) - 10} more", err=True)
    if result.errors and apply and not skip_failed:
        raise typer.Exit(code=1)


@review_app.command("fix-boilerplate")
def review_fix_boilerplate(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_ids_file: Path | None = typer.Option(
        None,
        "--item-ids-file",
        exists=True,
        help="Limit to tier-1 queue or subset (JSON list or review_queue.json)",
    ),
    queue_file: Path | None = typer.Option(
        None,
        "--queue-file",
        exists=True,
        help="Alias for --item-ids-file (review_queue.json from export-queue)",
    ),
    max_items: int | None = typer.Option(None, "--max-items"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List targets only"),
    feedback_file: Path | None = typer.Option(None, "--feedback-file", exists=True),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-item progress lines"),
) -> None:
    """Bulk-regenerate comparison items with boilerplate canonical answers via Gemini."""
    if not dry_run:
        try:
            GeminiItemGenerator.require_api_key()
        except RuntimeError as exc:
            raise typer.BadParameter(str(exc)) from exc
    ids_path = queue_file or item_ids_file
    feedback = (
        feedback_file.read_text(encoding="utf-8")
        if feedback_file
        else BOILERPLATE_REGEN_FEEDBACK
    )
    if dry_run:
        item_ids = _load_item_ids_file(ids_path) if ids_path else None
        targets = list_boilerplate_comparison_items(draft, item_ids=item_ids)
        if max_items:
            targets = targets[:max_items]
        typer.echo(f"Boilerplate comparison items: {len(targets)}")
        for item in targets[:20]:
            typer.echo(f"  {item.item_id}")
        if len(targets) > 20:
            typer.echo(f"  ... and {len(targets) - 20} more")
        return
    report = regenerate_boilerplate_items(
        draft,
        item_ids_file=ids_path,
        feedback=feedback,
        repo_root=REPO_ROOT,
        max_items=max_items,
        progress=None if quiet else _review_progress,
    )
    write_bulk_regenerate_report(draft, report)
    if quiet:
        typer.echo(
            f"fix-boilerplate: targeted={report.targeted} succeeded={report.succeeded} "
            f"failed={report.failed}"
        )
    if report.failures:
        typer.echo(f"First failure: {report.failures[0]}", err=True)
        raise typer.Exit(code=1)


@review_app.command("regenerate-items")
def review_regenerate_items(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_ids_file: Path = typer.Option(..., "--item-ids-file", exists=True),
    max_items: int | None = typer.Option(None, "--max-items"),
    feedback_file: Path | None = typer.Option(None, "--feedback-file", exists=True),
    dry_run: bool = typer.Option(False, "--dry-run"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-item progress lines"),
) -> None:
    """Bulk regenerate explicit item_ids (e.g. after CSV review)."""
    if not dry_run:
        try:
            GeminiItemGenerator.require_api_key()
        except RuntimeError as exc:
            raise typer.BadParameter(str(exc)) from exc
    feedback = feedback_file.read_text(encoding="utf-8") if feedback_file else ""
    report = regenerate_items_from_file(
        draft,
        item_ids_file,
        feedback=feedback,
        repo_root=REPO_ROOT,
        dry_run=dry_run,
        max_items=max_items,
        progress=None if quiet else _review_progress,
    )
    if not dry_run:
        write_bulk_regenerate_report(draft, report)
    if quiet or dry_run:
        typer.echo(
            f"regenerate-items: targeted={report.targeted} succeeded={report.succeeded} "
            f"failed={report.failed} dry_run={dry_run}"
        )


@review_app.command("export-pack")
def review_export_pack(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_ids: str | None = typer.Option(None, "--item-ids"),
    item_ids_file: Path | None = typer.Option(None, "--item-ids-file", exists=True),
    repro_input: Path | None = typer.Option(None, "--repro-input", exists=True, file_okay=False, dir_okay=True),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    variant: str = typer.Option("graph-full", "--variant"),
    max_items: int | None = typer.Option(None, "--max-items"),
) -> None:
    """Export HTML + CSV review pack for a subset of dev items."""
    ids: list[str] = []
    if item_ids:
        ids = [part.strip() for part in item_ids.split(",") if part.strip()]
    elif item_ids_file:
        ids = _load_item_ids_file(item_ids_file)
    else:
        raise typer.BadParameter("Provide --item-ids or --item-ids-file")
    if max_items:
        ids = ids[:max_items]
    dest = output_dir or draft / "review"
    html_path, csv_path = write_review_pack(
        draft,
        ids,
        dest,
        repro_input=repro_input,
        variant=variant,
    )
    typer.echo(f"Review pack -> {html_path}, {csv_path}")


@review_app.command("annotate")
def review_annotate(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_id: str = typer.Option(..., "--item-id"),
    failure_class: FailureClass = typer.Option(..., "--failure-class"),
    reviewer_id: str = typer.Option(..., "--reviewer-id"),
    notes: str = typer.Option("", "--notes"),
    corpus_spot_check: CorpusSpotCheckStatus = typer.Option(
        CorpusSpotCheckStatus.PENDING,
        "--corpus-spot-check",
    ),
    proposed_overrides_file: Path | None = typer.Option(None, "--proposed-overrides-file", exists=True),
) -> None:
    """Append one annotation record to annotations.jsonl."""
    resolve_draft_bundle(draft)
    overrides: ProposedOverrides | None = None
    if proposed_overrides_file:
        overrides = ProposedOverrides.model_validate(
            json.loads(proposed_overrides_file.read_text(encoding="utf-8"))
        )
    record = append_annotation(
        draft,
        item_id=item_id,
        reviewer_id=reviewer_id,
        failure_class=failure_class,
        notes=notes,
        corpus_spot_check=corpus_spot_check,
        proposed_overrides=overrides,
    )
    typer.echo(f"Annotation appended: {record.annotation_id} for {item_id}")


@review_app.command("apply-overrides")
def review_apply_overrides(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    annotation_ids: str | None = typer.Option(None, "--annotation-ids"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    skip_failed: bool = typer.Option(False, "--skip-failed"),
    force: bool = typer.Option(False, "--force", help="Allow agent_failure overrides"),
) -> None:
    """Merge approved annotations into items/dev.jsonl."""
    ids = None
    if annotation_ids:
        ids = {part.strip() for part in annotation_ids.split(",") if part.strip()}
    changelog = apply_overrides(
        draft,
        annotation_ids=ids,
        dry_run=dry_run,
        skip_failed=skip_failed,
        force_agent_failure=force,
    )
    accepted = sum(1 for entry in changelog if entry.validation_outcome == "accepted")
    rejected = sum(1 for entry in changelog if entry.validation_outcome == "rejected")
    typer.echo(f"Apply overrides: accepted={accepted} rejected={rejected} dry_run={dry_run}")
    if not dry_run and accepted:
        fixed_path = resolve_draft_bundle(draft) / "fixed_items.json"
        if fixed_path.is_file():
            typer.echo(f"fixed_items.json refreshed -> {fixed_path}")
    if rejected and not skip_failed and not dry_run:
        raise typer.Exit(code=1)


@review_app.command("summary")
def review_summary(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    repro_input: Path | None = typer.Option(None, "--repro-input", exists=True, file_okay=False, dir_okay=True),
    baseline_repro_input: Path | None = typer.Option(
        None,
        "--baseline-repro-input",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    variant: str = typer.Option("graph-full", "--variant"),
) -> None:
    """Emit quality_pass_summary.json from annotations and optional re-judge stats."""
    summary = build_quality_pass_summary(
        draft,
        repro_input=repro_input,
        baseline_repro_input=baseline_repro_input,
        variant=variant,
    )
    path = write_quality_pass_summary(draft, summary)
    typer.echo(f"Quality pass summary -> {path}")


@app.command("regenerate-item")
def regenerate_item_cmd(
    draft: Path = typer.Option(..., "--draft", exists=True, file_okay=False, dir_okay=True),
    item_id: str = typer.Option(..., "--item-id"),
    feedback_file: Path | None = typer.Option(None, "--feedback-file", exists=True),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Regenerate a single dev item via Gemini while preserving item_id."""
    feedback = feedback_file.read_text(encoding="utf-8") if feedback_file else ""
    item = regenerate_item(
        draft,
        item_id=item_id,
        feedback=feedback,
        repo_root=REPO_ROOT,
        dry_run=dry_run,
    )
    typer.echo(f"Regenerated {item.item_id} status={item.validation_status} dry_run={dry_run}")


@app.command("extend-quality")
def extend_quality(
    parent_version: str = typer.Option("2.0.0", "--parent-version"),
    config: Path = typer.Option(
        Path("configs/benchmarks/custom_judge_v2_quality.yaml"),
        "--config",
        "-c",
        exists=True,
        readable=True,
    ),
    run_id: str | None = typer.Option("quality-v2.0.1", "--run-id"),
) -> None:
    """Extend v2.0.0 into a quality draft with review sidecar files initialized."""
    extend(parent_version=parent_version, config=config, run_id=run_id)
    cfg = load_generation_config(config, base=REPO_ROOT)
    draft = Path(cfg.output.drafts_root) / (run_id or "quality-v2.0.1")
    for name in ("annotations.jsonl", "override_changelog.jsonl", "duplicate_feedback.jsonl"):
        path = draft / name
        if not path.exists():
            path.touch()
    typer.echo(f"Quality draft sidecars initialized at {draft}")
