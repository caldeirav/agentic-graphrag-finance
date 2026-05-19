"""Live SEC XBRL ingestion layer (EDGAR only)."""

from __future__ import annotations

import logging

from ingestion.cache_manager import atomic_write_package, lookup_cache, save_package, update_index
from ingestion.edgar_client import resolve_from_input, resolve_identifier
from ingestion.settings import ConfigurationError, require_edgar_user_agent
from ingestion.validators import ValidationError
from ingestion.xbrl_downloader import download_artifacts, package_dir, write_manifest
from models.ingestion import CacheEntry, FetchJob, FetchJobStatus, IssuerIdentifierInput

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigurationError",
    "ValidationError",
    "require_edgar_user_agent",
    "resolve_identifier",
    "resolve_from_input",
    "fetch_filing",
    "CacheEntry",
    "FetchJob",
]


def fetch_filing(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
    form_type: str = "10-K",
    force_refresh: bool = False,
) -> CacheEntry:
    """Resolve filing, download XBRL package from EDGAR, validate, and cache."""
    require_edgar_user_agent()
    resolution = resolve_identifier(
        ticker=ticker,
        cik=cik,
        accession=accession,
        form_type=form_type,
    )

    if not force_refresh:
        cached = lookup_cache(resolution)
        if cached is not None:
            logger.info("cache hit for %s", resolution.accession)
            return cached

    dest = package_dir(resolution)

    def _write(tmp):
        manifest = download_artifacts(resolution, tmp)
        write_manifest(tmp, manifest)

    atomic_write_package(dest, _write)
    manifest_path = dest / "manifest.json"
    from models.ingestion import XBRLArtifactManifest

    manifest = XBRLArtifactManifest.model_validate_json(manifest_path.read_text())
    entry = save_package(resolution, manifest, dest=dest)
    update_index(entry, resolution)
    return entry


def start_fetch_job(ident: IssuerIdentifierInput, form_type: str = "10-K") -> FetchJob:
    job_id = f"fetch-{ident.ticker or ident.cik or ident.accession}"
    try:
        resolution = resolve_from_input(ident, form_type=form_type)
        return FetchJob(job_id=job_id, status=FetchJobStatus.PENDING, resolution=resolution)
    except Exception as exc:
        return FetchJob(job_id=job_id, status=FetchJobStatus.FAILED, error=str(exc))
