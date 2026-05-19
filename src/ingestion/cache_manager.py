"""Local cache for SEC XBRL download packages."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ingestion.package_utils import is_mock_package, package_has_substantive_content
from ingestion.settings import get_settings, is_mock_mode
from ingestion.validators import validate_manifest
from ingestion.xbrl_downloader import package_dir, write_manifest
from models.ingestion import CacheEntry, FilingResolution, XBRLArtifactManifest

logger = logging.getLogger(__name__)


def _hash_directory(path: Path) -> str:
    h = hashlib.sha256()
    for fp in sorted(path.rglob("*")):
        if fp.is_file() and fp.name != "manifest.json":
            h.update(fp.name.encode())
            h.update(fp.read_bytes())
    return h.hexdigest()


def _load_manifest(path: Path) -> XBRLArtifactManifest | None:
    if not path.exists():
        return None
    return XBRLArtifactManifest.model_validate_json(path.read_text())


def lookup_cache(resolution: FilingResolution) -> CacheEntry | None:
    dest = package_dir(resolution)
    manifest_path = dest / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = _load_manifest(manifest_path)
    if manifest is None or not manifest.complete:
        return None
    if is_mock_package(manifest) and not is_mock_mode():
        logger.info("ignoring mock cache for %s (live mode)", resolution.accession)
        return None
    if not package_has_substantive_content(dest, manifest):
        logger.info("ignoring empty cache for %s", resolution.accession)
        return None
    try:
        validate_manifest(manifest, dest)
    except ValueError:
        logger.info("cache invalid for %s", resolution.accession)
        return None
    return CacheEntry(
        local_path=dest,
        manifest_path=manifest_path,
        content_hash=_hash_directory(dest),
        parse_ready=True,
        cached_at=datetime.now(UTC),
        cache_hit=True,
    )


def atomic_write_package(dest: Path, write_fn) -> Path:
    """Write to temp dir then rename (T024)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        tmp_path = Path(tmp)
        write_fn(tmp_path)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(tmp_path), str(dest))
    logger.info("cached package at %s", dest)
    return dest


def save_package(
    resolution: FilingResolution,
    manifest: XBRLArtifactManifest,
    *,
    dest: Path | None = None,
) -> CacheEntry:
    target = dest or package_dir(resolution)
    manifest_path = target / "manifest.json"
    write_manifest(target, manifest)
    validate_manifest(manifest, target)
    complete = manifest.model_copy(update={"complete": True})
    write_manifest(target, complete)
    return CacheEntry(
        local_path=target,
        manifest_path=manifest_path,
        content_hash=_hash_directory(target),
        parse_ready=True,
        cached_at=datetime.now(UTC),
        cache_hit=False,
    )


def cache_metadata_path() -> Path:
    return get_settings().sec_downloads_root / ".cache_index.json"


def update_index(entry: CacheEntry, resolution: FilingResolution) -> None:
    idx_path = cache_metadata_path()
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    data[resolution.accession] = {
        "content_hash": entry.content_hash,
        "path": str(entry.local_path),
        "cached_at": entry.cached_at.isoformat(),
    }
    idx_path.write_text(json.dumps(data, indent=2))
