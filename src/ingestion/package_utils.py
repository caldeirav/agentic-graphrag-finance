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
