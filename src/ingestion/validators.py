"""Validate downloaded XBRL packages."""

from __future__ import annotations

from pathlib import Path

from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole


class ValidationError(ValueError):
    """XBRL package failed validation."""


def validate_manifest(manifest: XBRLArtifactManifest, root: Path) -> None:
    roles = {a.role for a in manifest.artifacts}
    if XBRLArtifactRole.INSTANCE not in roles:
        raise ValidationError("Missing instance document in manifest")
    for art in manifest.artifacts:
        path = root / art.filename
        if not path.exists():
            raise ValidationError(f"Missing artifact on disk: {art.filename}")
        if art.role == XBRLArtifactRole.INSTANCE and path.stat().st_size == 0:
            raise ValidationError(f"Empty instance file: {art.filename}")
    xsd_present = any(a.role == XBRLArtifactRole.SCHEMA for a in manifest.artifacts)
    if not xsd_present:
        raise ValidationError("Missing taxonomy schema (.xsd) in package")
