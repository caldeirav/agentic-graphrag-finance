"""Bundle path helpers for dataset quality review (018)."""

from __future__ import annotations

from pathlib import Path


def resolve_draft_bundle(path: Path) -> Path:
    """Validate bundle root contains a dev split and return resolved path."""
    root = path.expanduser().resolve()
    if not root.is_dir():
        msg = f"Bundle root is not a directory: {root}"
        raise FileNotFoundError(msg)
    items_path = root / "items" / "dev.jsonl"
    if not items_path.is_file():
        msg = f"Missing dev split at {items_path}"
        raise FileNotFoundError(msg)
    return root


def resolve_release_bundle(
    repo_root: Path,
    *,
    bundle_rel_path: str,
    version: str,
    draft: Path | None = None,
) -> Path:
    """Resolve published bundle path, falling back to quality draft when unpublished."""
    if draft is not None:
        return resolve_draft_bundle(draft)
    published = (repo_root / bundle_rel_path).resolve()
    if published.is_dir() and (published / "items" / "dev.jsonl").is_file():
        return published
    draft_candidates = [
        repo_root / "data/benchmarks/custom-judge/drafts" / f"quality-v{version}",
        repo_root / "data/benchmarks/custom-judge/drafts" / f"quality-{version}",
    ]
    for draft_candidate in draft_candidates:
        resolved = draft_candidate.resolve()
        if resolved.is_dir():
            return resolve_draft_bundle(resolved)
    return resolve_draft_bundle(published)
