"""Validate downloaded XBRL packages."""

from __future__ import annotations

from pathlib import Path

from ingestion.package_utils import MIN_INSTANCE_BYTES
from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole


class ValidationError(ValueError):
    """XBRL package failed validation."""


def validate_manifest(manifest: XBRLArtifactManifest, root: Path) -> None:
    roles = {a.role for a in manifest.artifacts}

    for art in manifest.artifacts:
        path = root / art.filename
        if not path.exists():
            raise ValidationError(f"Missing artifact on disk: {art.filename}")
        if art.role == XBRLArtifactRole.INSTANCE and path.stat().st_size == 0:
            raise ValidationError(f"Empty instance file: {art.filename}")

    if XBRLArtifactRole.XBRL_ZIP in roles:
        for art in manifest.artifacts:
            if art.role == XBRLArtifactRole.XBRL_ZIP:
                zp = root / art.filename
                if zp.stat().st_size < 1_000:
                    raise ValidationError(f"XBRL zip too small: {art.filename}")

    if XBRLArtifactRole.INSTANCE not in roles:
        raise ValidationError("Missing instance document in manifest")
    instance_ok = False
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            if (root / art.filename).stat().st_size >= MIN_INSTANCE_BYTES:
                instance_ok = True
    if not instance_ok:
        for path in root.rglob("*_htm.xml"):
            if path.is_file() and path.stat().st_size >= MIN_INSTANCE_BYTES:
                instance_ok = True
                break
    if not instance_ok:
        raise ValidationError("XBRL instance document is too small to parse")

    xsd_present = any(a.role == XBRLArtifactRole.SCHEMA for a in manifest.artifacts)
    if not xsd_present:
        for path in root.rglob("*.xsd"):
            if path.is_file():
                xsd_present = True
                break
    if not xsd_present:
        raise ValidationError("Missing taxonomy schema (.xsd) in package")
