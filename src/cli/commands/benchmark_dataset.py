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
from evaluation.generation.bundle import publish_draft, write_draft_manifest
from evaluation.generation.config_loader import load_allowlist, load_generation_config
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.judge_generator import generate_items, write_items_jsonl
from evaluation.generation.sampler import (
    run_sampling,
    sampling_manifest_hash,
)
from models.benchmark_generation import DatasetManifest, SamplingManifest

app = typer.Typer(
    name="benchmark-dataset",
    help="Generate, publish, and reproduce custom-judge evaluation datasets",
    no_args_is_help=True,
)

CI_CONFIG_ID = "custom_judge_ci"
LIVE_CONFIG_ID = "custom_judge_live"
REPO_ROOT = Path(__file__).resolve().parents[3]


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
        write_items_jsonl(accepted, items_path)
        write_draft_manifest(
            draft_dir=draft,
            config=cfg,
            sampling=sampling,
            bundle=bundle,
            report=report,
            items_path=items_path,
        )
        reporter.phase_end(
            "judge",
            f"accepted={report.accepted_count} rejected={report.rejected_count} "
            f"pass_rate={report.pass_rate:.0%}",
        )
        reporter.summary(
            "Generate complete",
            [
                f"draft={draft}",
                f"accepted={report.accepted_count}/{report.candidates_total}",
                f"pass_rate={report.pass_rate:.1%}",
                f"judge_api_calls={report.judge_api_calls}",
                f"duration={report.duration_seconds:.1f}s",
                f"items={items_path}",
            ],
        )


@app.command("publish")
def publish(
    draft_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    version: str = typer.Option(..., "--version", help="Semver version to publish"),
    min_items: int = typer.Option(200, "--min-items"),
    skip_gates: bool = typer.Option(False, "--skip-gates", help="Skip item count/pass-rate gates"),
) -> None:
    """Promote a draft bundle to a published version."""
    cfg = load_generation_config(draft_dir / "generation_config.yaml", base=REPO_ROOT)
    dest = publish_draft(
        draft_dir,
        version=version,
        published_root=Path(cfg.output.published_root),
        min_items=1 if skip_gates else min_items,
        skip_gates=skip_gates,
    )
    typer.echo(f"Published custom-judge v{version} -> {dest}")


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
