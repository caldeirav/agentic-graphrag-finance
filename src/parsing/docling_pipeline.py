"""Docling XBRL parsing (mandatory; no HTML fallback)."""

from __future__ import annotations

from pathlib import Path

from models.filing import FilingRef
from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole
from models.parsing import ParsedDocument
from parsing.docling_xbrl import is_xbrl_instance_path, parse_xbrl_instance
from parsing.errors import ParseError


def find_primary_parse_path(root: Path, manifest: XBRLArtifactManifest) -> Path:
    """XBRL instance document is the only parse source."""
    return find_primary_instance_path(root, manifest)


def find_primary_instance_path(root: Path, manifest: XBRLArtifactManifest) -> Path:
    """Locate primary XBRL instance XML (largest *_htm.xml / instance role)."""
    candidates: list[Path] = []
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            path = root / art.filename
            if path.is_file():
                candidates.append(path)
    for path in root.rglob("*_htm.xml"):
        if path.is_file():
            candidates.append(path)
    for path in root.rglob("*.xml"):
        if path.is_file() and "htm" in path.name.lower():
            candidates.append(path)
    if not candidates:
        for path in sorted(root.glob("*.xml")):
            if path.is_file():
                candidates.append(path)
    if not candidates:
        raise FileNotFoundError(f"No instance XML under {root}")
    return max(candidates, key=lambda p: p.stat().st_size)


def parse_filing_path(
    path: Path,
    filing: FilingRef,
    *,
    package_root: Path | None = None,
    config_path: Path | None = None,
) -> ParsedDocument:
    """Parse an XBRL instance into ParsedDocument using Docling XML_XBRL."""
    if not is_xbrl_instance_path(path):
        raise ParseError(
            f"Refusing non-XBRL input {path.name}; ingest EDGAR XBRL packages only."
        )
    root = package_root or path.parent
    parsed = parse_xbrl_instance(path, root, filing, config_path=config_path)
    if parsed is None:
        raise ParseError(f"Docling XBRL conversion produced no content for {path}")
    return parsed
