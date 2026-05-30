"""Corpus hash verification for offline reproduction (012)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.reproduction.manifest import sha256_file
from models.benchmark_generation import DatasetManifest
from models.reproduction import ReleaseManifest

_TBD_HASH_VALUES = frozenset({"", "TBD", "sha256:TBD"})


@dataclass
class CorpusVerifyResult:
    ok: bool
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    lfs_hints: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        if self.ok:
            return "All corpus hashes verified."
        lines = ["Corpus verification failed:"]
        for path in self.missing:
            lines.append(f"  missing: {path}")
            hint = _lfs_hint(path)
            if hint:
                lines.append(f"    try: {hint}")
        for hint in self.lfs_hints:
            if hint not in lines:
                lines.append(f"  lfs hint: {hint}")
        for path in self.mismatched:
            lines.append(f"  hash mismatch: {path}")
        return "\n".join(lines)


def _lfs_hint(relative_path: str) -> str:
    if "custom-judge" in relative_path:
        return "git lfs pull --include='data/benchmarks/custom-judge/**/corpus/**'"
    return "git lfs pull"


def _normalize_hash(value: str) -> str:
    value = value.strip()
    if value.startswith("sha256:"):
        return value.lower()
    return f"sha256:{value.lower()}"


def resolve_corpus_hashes(manifest: ReleaseManifest, bundle_root: Path) -> dict[str, str]:
    """Release manifest hashes, falling back to bundle manifest artifact_hashes."""
    resolved: dict[str, str] = {}
    for rel_path, expected in manifest.corpus_hashes.items():
        if expected not in _TBD_HASH_VALUES:
            resolved[rel_path] = expected
    if resolved:
        return resolved
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.is_file():
        return resolved
    bundle_manifest = DatasetManifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    return dict(bundle_manifest.corpus_bundle.artifact_hashes)


def verify_corpus_hashes(
    manifest: ReleaseManifest,
    *,
    repo_root: Path | None = None,
) -> CorpusVerifyResult:
    root = repo_root or Path.cwd()
    bundle_root = root / manifest.custom_judge_bundle_path
    corpus_hashes = resolve_corpus_hashes(manifest, bundle_root)
    if not corpus_hashes:
        msg = (
            f"No corpus hashes in release manifest or bundle at {bundle_root / 'manifest.json'}. "
            "Run benchmark-dataset generate first or populate corpus_hashes."
        )
        raise FileNotFoundError(msg)
    missing: list[str] = []
    mismatched: list[str] = []

    for rel_path, expected in corpus_hashes.items():
        artifact = bundle_root / rel_path
        if not artifact.is_file():
            missing.append(str(artifact.relative_to(root) if artifact.is_relative_to(root) else artifact))
            continue
        actual = _normalize_hash(sha256_file(artifact))
        if actual != _normalize_hash(expected):
            mismatched.append(rel_path)

    hints = sorted({_lfs_hint(p) for p in missing if _lfs_hint(p)})

    return CorpusVerifyResult(
        ok=not missing and not mismatched,
        missing=missing,
        mismatched=mismatched,
        lfs_hints=hints,
    )


def dry_run_registry_check(manifest: ReleaseManifest, *, repo_root: Path | None = None) -> None:
    """Load custom-judge split header without running eval items."""
    root = repo_root or Path.cwd()
    bundle = root / manifest.custom_judge_bundle_path
    ds = CustomJudgeDataset(version=manifest.custom_judge_version, bundle_root=bundle)
    ds.manifest()
    split_path = bundle / "items" / f"{manifest.eval_split}.jsonl"
    if not split_path.is_file():
        msg = f"Eval split missing: {split_path}"
        raise FileNotFoundError(msg)
