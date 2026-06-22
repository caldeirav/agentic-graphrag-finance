"""Load and validate reproduction output bundles for report generation (014)."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.generation.bundle_version import is_v2_or_later
from evaluation.generation.review._paths import resolve_release_bundle
from evaluation.reproduction.manifest import load_release_manifest
from evaluation.reproduction.report_errors import ReportInputError
from evaluation.reproduction.report_models import (
    CSV_HEADERS,
    OPTIONAL_PAPER_TABLE_IDS,
    PAPER_TABLE_IDS,
    REQUIRED_PAPER_TABLE_IDS,
    ItemResultRecord,
    PaperTableId,
    ReproOutputBundle,
    TableData,
)
from models.evaluation import BenchmarkResult
from models.reproduction import ReproRun

_ANSWER_EXCERPT_LEN = 280
_RESERVED_DIRS = frozenset({"tables", "assets", "__pycache__"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path, table_id: PaperTableId) -> TableData:
    expected = CSV_HEADERS[table_id]
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != list(expected):
            raise ReportInputError(
                f"CSV header mismatch in {path.name}; expected {list(expected)}, "
                f"got {reader.fieldnames}",
                path=path,
            )
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return TableData(columns=list(expected), rows=rows)


def _discover_variant_dirs(output_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in output_dir.iterdir()
        if p.is_dir() and p.name not in _RESERVED_DIRS and not p.name.startswith(".")
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _truncate_answer(text: str, limit: int = _ANSWER_EXCERPT_LEN) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _load_item_metadata(
    release_manifest: dict[str, Any] | None,
    *,
    repo_root: Path,
) -> dict[str, dict[str, str]]:
    """Load question and expected answer from the custom-judge bundle when available."""
    if not release_manifest:
        return {}
    bundle_rel = release_manifest.get("custom_judge_bundle_path")
    version = str(release_manifest.get("custom_judge_version") or "")
    if not bundle_rel:
        return {}
    split = str(release_manifest.get("eval_split") or "dev")
    bundle_root = resolve_release_bundle(
        repo_root,
        bundle_rel_path=str(bundle_rel),
        version=version,
    )
    items_path = bundle_root / "items" / f"{split}.jsonl"
    if not items_path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    for line in items_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gt = row.get("ground_truth") or {}
        answer = str(gt.get("answer") or "").strip()
        out[str(row["item_id"])] = {
            "question": str(row.get("question") or "").strip(),
            "expected_answer": answer,
            "inspiration_profile": str(row.get("inspiration_profile") or "").strip(),
        }
    return out


def _map_benchmark_result(
    variant_id: str,
    result: BenchmarkResult,
    *,
    source_path: Path,
    item_metadata: dict[str, dict[str, str]] | None = None,
) -> ItemResultRecord:
    meta = (item_metadata or {}).get(result.item_id, {})
    inspiration_profile = meta.get("inspiration_profile", "")
    answer = result.answer
    full_text = answer.text if answer and answer.text else ""
    excerpt = _truncate_answer(full_text) if full_text else ""
    citation_count = len(answer.citations) if answer and answer.citations else 0
    rubric: dict[str, float] = {}
    if result.judge_verdict and result.judge_verdict.scores:
        rubric = {k: float(v) for k, v in result.judge_verdict.scores.items()}
    failure = ""
    judge_rationale = ""
    if result.judge_verdict and result.judge_verdict.rationale:
        judge_rationale = result.judge_verdict.rationale.strip()
    if result.judge_status in {"degraded", "not_evaluable", "pending"}:
        failure = judge_rationale or result.judge_status
    elif (result.validation_status or "").lower() in {"incomplete", "non_reproducible"}:
        failure = result.validation_status
    flags: list[str] = []
    if result.judge_status:
        flags.append(result.judge_status)
    ranking = result.ranking_metrics
    return ItemResultRecord(
        variant_id=variant_id,
        item_id=result.item_id,
        inspiration_profile=inspiration_profile,
        question=meta.get("question", ""),
        expected_answer=meta.get("expected_answer", ""),
        judge_status=result.judge_status or "",
        validation_status=result.validation_status or "",
        outcome_score=result.outcome_score,
        mrr=ranking.mrr if ranking is not None else None,
        map_score=ranking.map_score if ranking is not None else None,
        ndcg_at_10=ranking.ndcg_at_10 if ranking is not None else None,
        trajectory_fidelity=result.trajectory_fidelity,
        rubric_scores=rubric,
        structural_metrics={},
        failure_reason=failure,
        answer_excerpt=excerpt,
        answer_text=full_text,
        judge_rationale=judge_rationale,
        citation_count=citation_count,
        trajectory_ref=result.mlflow_run_id or "see source JSON",
        source_path=str(source_path),
        flags=flags,
    )


def load_variant_item_records(bundle: ReproOutputBundle) -> dict[str, list[ItemResultRecord]]:
    """Parse per-variant results.json into drill-down records."""
    out: dict[str, list[ItemResultRecord]] = {}
    for variant_id, records in bundle.variant_results.items():
        out[variant_id] = records
    return out


def load_repro_report_bundle(
    input_dir: Path,
    *,
    manifest_path: Path | None = None,
) -> ReproOutputBundle:
    """Load repro artifacts; hard-fail on missing required CSVs/run state."""
    root = input_dir.resolve()
    if not root.is_dir():
        raise ReportInputError("Input directory does not exist", path=root)

    repro_path = root / "repro_run.json"
    if not repro_path.is_file():
        raise ReportInputError("Missing required repro_run.json", path=repro_path)

    repro_run = ReproRun.model_validate(json.loads(repro_path.read_text(encoding="utf-8")))

    tables_dir = root / "tables"
    if not tables_dir.is_dir():
        raise ReportInputError("Missing required tables/ directory", path=tables_dir)

    tables: dict[str, TableData] = {}
    warnings: list[str] = []
    for table_id in REQUIRED_PAPER_TABLE_IDS:
        csv_path = tables_dir / f"{table_id.value}.csv"
        if not csv_path.is_file():
            raise ReportInputError(f"Missing required {csv_path.name}", path=csv_path)
        tables[table_id.value] = _read_csv(csv_path, table_id)
    for table_id in OPTIONAL_PAPER_TABLE_IDS:
        csv_path = tables_dir / f"{table_id.value}.csv"
        if csv_path.is_file():
            tables[table_id.value] = _read_csv(csv_path, table_id)
        elif table_id in (PaperTableId.BY_EVIDENCE_SOURCE, PaperTableId.BY_PROFILE):
            warnings.append(
                f"Optional {csv_path.name} not found; outcome-by-"
                f"{'stratum' if table_id == PaperTableId.BY_EVIDENCE_SOURCE else 'profile'} "
                "report section will be omitted"
            )

    incomplete_variants: list[str] = []
    variant_results: dict[str, list[ItemResultRecord]] = {}

    repo_root = Path(__file__).resolve().parents[3]
    item_metadata: dict[str, dict[str, str]] = {}
    release_manifest: dict[str, Any] | None = None
    resolved_manifest = manifest_path
    if resolved_manifest is None:
        tag_candidate = repo_root / "releases" / repro_run.release_tag / "manifest.yaml"
        if tag_candidate.is_file():
            resolved_manifest = tag_candidate
    if resolved_manifest and resolved_manifest.is_file():
        try:
            rel = load_release_manifest(resolved_manifest)
            release_manifest = rel.model_dump(mode="json")
            item_metadata = _load_item_metadata(release_manifest, repo_root=repo_root)
        except Exception as exc:  # noqa: BLE001 — surface as warning, not hard fail
            warnings.append(f"Could not load release manifest: {exc}")
    elif manifest_path is not None:
        warnings.append(f"Release manifest not found at {manifest_path}")
    else:
        warnings.append("Release manifest unavailable")

    known_from_run = {vr.variant_id for vr in repro_run.variant_runs}
    variant_dirs = _discover_variant_dirs(root)
    seen_variants = set()

    for variant_dir in variant_dirs:
        variant_id = variant_dir.name
        seen_variants.add(variant_id)
        results_path = variant_dir / "results.json"
        if not results_path.is_file():
            incomplete_variants.append(variant_id)
            warnings.append(
                f"Variant '{variant_id}' has no results.json; drill-down omitted "
                f"({results_path})"
            )
            continue
        raw = json.loads(results_path.read_text(encoding="utf-8"))
        records = [
            _map_benchmark_result(
                variant_id,
                BenchmarkResult.model_validate(row),
                source_path=results_path,
                item_metadata=item_metadata,
            )
            for row in raw
        ]
        variant_results[variant_id] = records

    for variant_id in sorted(known_from_run - seen_variants):
        incomplete_variants.append(variant_id)
        warnings.append(f"Variant directory missing for '{variant_id}'")

    headline_tex_path = tables_dir / "headline.tex"
    headline_tex: str | None = None
    if headline_tex_path.is_file():
        headline_tex = headline_tex_path.read_text(encoding="utf-8")
    else:
        warnings.append(f"Optional {headline_tex_path.name} not found")

    export_manifest = _load_optional_json(root / "export_manifest.json")
    if export_manifest is None:
        warnings.append("Optional export_manifest.json not found")

    return ReproOutputBundle(
        output_dir=root,
        repro_run=repro_run,
        tables=tables,
        variant_results=variant_results,
        item_metadata=item_metadata,
        release_manifest=release_manifest,
        export_manifest=export_manifest,
        headline_tex=headline_tex,
        warnings=warnings,
        incomplete_variants=incomplete_variants,
    )


def custom_judge_version_for_bundle(bundle: ReproOutputBundle) -> str | None:
    if bundle.export_manifest:
        version = bundle.export_manifest.get("custom_judge_version")
        if version:
            return str(version)
    if bundle.release_manifest:
        version = bundle.release_manifest.get("custom_judge_version")
        if version:
            return str(version)
    return None


def is_v2_repro_bundle(bundle: ReproOutputBundle) -> bool:
    version = custom_judge_version_for_bundle(bundle)
    return bool(version and is_v2_or_later(version))


def bundle_source_hashes(bundle: ReproOutputBundle) -> dict[str, str]:
    """Integrity hashes for loaded inputs."""
    hashes: dict[str, str] = {}
    repro_path = bundle.output_dir / "repro_run.json"
    if repro_path.is_file():
        hashes["repro_run.json"] = _sha256(repro_path)
    for table_id in PAPER_TABLE_IDS:
        path = bundle.output_dir / "tables" / f"{table_id.value}.csv"
        if path.is_file():
            hashes[path.name] = _sha256(path)
    return hashes
