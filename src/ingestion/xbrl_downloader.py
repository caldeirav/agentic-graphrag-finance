"""Download XBRL instance and taxonomy artifacts from SEC EDGAR."""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from ingestion.edgar_xbrl import download_edgar_xbrl_package
from ingestion.settings import get_settings, is_fixture_ingestion
from models.ingestion import FilingResolution, XBRLArtifact, XBRLArtifactManifest

logger = logging.getLogger(__name__)


def _fixture_source_dir(resolution: FilingResolution) -> Path:
    root = get_settings().fixture_downloads_root
    return root / resolution.ticker.upper() / resolution.accession


def _copy_fixture_package(resolution: FilingResolution, dest: Path) -> list[XBRLArtifact]:
    src = _fixture_source_dir(resolution)
    if not src.is_dir():
        raise FileNotFoundError(f"Fixture package not found: {src}")
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.iterdir():
        if path.is_file():
            shutil.copy2(path, dest / path.name)
    artifacts: list[XBRLArtifact] = []
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rel = path.relative_to(dest)
        from ingestion.edgar_xbrl import classify_filename, is_xbrl_package_file

        if is_xbrl_package_file(path.name):
            artifacts.append(
                XBRLArtifact(
                    filename=str(rel),
                    role=classify_filename(path.name),
                    url=f"fixture://{rel}",
                )
            )
    if not artifacts:
        raise RuntimeError(f"No XBRL files in fixture package {src}")
    return artifacts


def download_artifacts(
    resolution: FilingResolution,
    dest: Path,
    artifacts: list[XBRLArtifact] | None = None,
) -> XBRLArtifactManifest:
    dest.mkdir(parents=True, exist_ok=True)

    if is_fixture_ingestion():
        arts = artifacts or _copy_fixture_package(resolution, dest)
    else:
        arts = list(download_edgar_xbrl_package(resolution, dest))

    updated: list[XBRLArtifact] = []
    for art in arts:
        path = dest / art.filename
        h = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        updated.append(art.model_copy(update={"content_hash": h}))

    return XBRLArtifactManifest(resolution=resolution, artifacts=updated, complete=False)


def write_manifest(dest: Path, manifest: XBRLArtifactManifest) -> Path:
    path = dest / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def package_dir(resolution: FilingResolution) -> Path:
    root = get_settings().sec_downloads_root
    return root / resolution.ticker.upper() / resolution.accession
