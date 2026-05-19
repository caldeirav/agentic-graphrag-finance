"""Validate downloaded XBRL packages."""

from __future__ import annotations

from pathlib import Path

from ingestion.package_utils import MIN_FILING_HTML_BYTES, MIN_INSTANCE_BYTES, primary_html_path
from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole


class ValidationError(ValueError):
    """XBRL package failed validation."""


def validate_manifest(manifest: XBRLArtifactManifest, root: Path) -> None:
    roles = {a.role for a in manifest.artifacts}
    has_html = XBRLArtifactRole.FILING_HTML in roles

    for art in manifest.artifacts:
        path = root / art.filename
        if not path.exists():
            raise ValidationError(f"Missing artifact on disk: {art.filename}")
        if art.role == XBRLArtifactRole.FILING_HTML and path.stat().st_size < MIN_FILING_HTML_BYTES:
            raise ValidationError(
                f"Filing HTML too small ({path.stat().st_size} bytes): {art.filename}"
            )
        if art.role == XBRLArtifactRole.INSTANCE and path.stat().st_size == 0:
            raise ValidationError(f"Empty instance file: {art.filename}")

    if has_html:
        html_path = primary_html_path(root, manifest)
        if html_path is None:
            raise ValidationError("Filing HTML artifact missing on disk")
        return

    if XBRLArtifactRole.INSTANCE not in roles:
        raise ValidationError("Missing instance document in manifest")
    instance_ok = False
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            if (root / art.filename).stat().st_size >= MIN_INSTANCE_BYTES:
                instance_ok = True
    if not instance_ok:
        raise ValidationError("XBRL instance document is too small to parse")

    xsd_present = any(a.role == XBRLArtifactRole.SCHEMA for a in manifest.artifacts)
    if not xsd_present:
        raise ValidationError("Missing taxonomy schema (.xsd) in package")
