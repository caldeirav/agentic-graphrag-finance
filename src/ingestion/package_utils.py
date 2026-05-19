"""Helpers for download package validation and cache policy."""

from __future__ import annotations

from pathlib import Path

from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole

MIN_FILING_HTML_BYTES = 5_000
MIN_INSTANCE_BYTES = 1_000


def is_mock_package(manifest: XBRLArtifactManifest) -> bool:
    """True if package was produced by test-mock ingestion (not live SEC content)."""
    url = manifest.resolution.sec_api_filing_url or ""
    if "mock://" in url or "sec.gov/mock" in url:
        return True
    return any((a.url or "").startswith("mock://") for a in manifest.artifacts)


def primary_html_path(root: Path, manifest: XBRLArtifactManifest) -> Path | None:
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.FILING_HTML:
            path = root / art.filename
            if path.is_file():
                return path
    return None


def package_has_substantive_content(root: Path, manifest: XBRLArtifactManifest) -> bool:
    html = primary_html_path(root, manifest)
    if html is not None and html.stat().st_size >= MIN_FILING_HTML_BYTES:
        return True
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            path = root / art.filename
            if path.is_file() and path.stat().st_size >= MIN_INSTANCE_BYTES:
                return True
    return False
