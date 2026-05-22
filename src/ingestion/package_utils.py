"""Helpers for download package validation and cache policy."""

from __future__ import annotations

from pathlib import Path

from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole

MIN_INSTANCE_BYTES = 1_000


def is_fixture_package(manifest: XBRLArtifactManifest) -> bool:
    """True if package came from tests/fixtures (not live EDGAR download)."""
    url = manifest.resolution.edgar_filing_url or ""
    if url.startswith("fixture://"):
        return True
    return any((a.url or "").startswith("fixture://") for a in manifest.artifacts)


def xbrl_package_is_complete(root: Path, manifest: XBRLArtifactManifest) -> bool:
    """True when package satisfies XBRL completeness (instance + schema)."""
    from ingestion.validators import validate_manifest

    if not manifest.complete:
        return False
    try:
        validate_manifest(manifest, root)
        return True
    except ValueError:
        return False


def find_narrative_html_candidate(
    root: Path,
    manifest: XBRLArtifactManifest,
    *,
    min_bytes: int = 5000,
) -> Path | None:
    """Locate filing .htm or inline/iXBRL suitable for narrative extraction."""
    import re

    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.FILING_HTML:
            path = root / art.filename
            if path.is_file() and path.stat().st_size >= min_bytes:
                return path
    for path in sorted(root.rglob("*.htm")):
        if not path.is_file() or path.stat().st_size < min_bytes:
            continue
        name = path.name.lower()
        if name.startswith("a10-k") or re.match(r"^r\d+\.htm$", name):
            continue
        if re.search(r"-\d{8}\.htm$", name) or "exhibit" not in name:
            return path
    for path in sorted(root.rglob("*_htm.xml")):
        if path.is_file() and path.stat().st_size >= min_bytes:
            return path
    return None


def package_has_substantive_content(root: Path, manifest: XBRLArtifactManifest) -> bool:
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            path = root / art.filename
            if path.is_file() and path.stat().st_size >= MIN_INSTANCE_BYTES:
                return True
    for path in root.rglob("*_htm.xml"):
        if path.is_file() and path.stat().st_size >= MIN_INSTANCE_BYTES:
            return True
    return any(a.role == XBRLArtifactRole.XBRL_ZIP for a in manifest.artifacts)
