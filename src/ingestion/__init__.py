"""Live SEC XBRL ingestion layer (EDGAR only)."""

from __future__ import annotations

import logging
from pathlib import Path

from ingestion.cache_manager import atomic_write_package, lookup_cache, save_package, update_index
from ingestion.edgar_client import list_recent_filings, resolve_from_input, resolve_identifier
from ingestion.settings import ConfigurationError, require_edgar_user_agent
from ingestion.validators import ValidationError
from ingestion.xbrl_downloader import download_artifacts, package_dir, write_manifest
from models.ingestion import CacheEntry, FetchJob, FetchJobStatus, FilingResolution, IssuerIdentifierInput

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigurationError",
    "ValidationError",
    "CorpusCapExceededError",
    "require_edgar_user_agent",
    "resolve_identifier",
    "resolve_from_input",
    "list_recent_filings",
    "fetch_filing",
    "default_corpus_definition",
    "resolve_corpus_members",
    "materialize_corpus_members",
    "CacheEntry",
    "FetchJob",
]


def _sync_manifest_resolution(dest: Path, resolution: FilingResolution) -> None:
    """Update cached manifest when EDGAR dates were previously stubbed (accession-only resolve)."""
    from models.ingestion import XBRLArtifactManifest

    manifest_path = dest / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = XBRLArtifactManifest.model_validate_json(manifest_path.read_text())
    stored = manifest.resolution
    if stored.filed_at == resolution.filed_at and stored.period_end == resolution.period_end:
        return
    manifest = manifest.model_copy(update={"resolution": resolution})
    write_manifest(dest, manifest)
    logger.info("updated manifest dates for %s", resolution.accession)


def fetch_filing(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
    form_type: str = "10-K",
    resolution: FilingResolution | None = None,
    force_refresh: bool = False,
    skip_html_narrative: bool = False,
) -> CacheEntry:
    """Resolve filing, download XBRL package from EDGAR, validate, and cache."""
    require_edgar_user_agent()
    resolution = resolution or resolve_identifier(
        ticker=ticker,
        cik=cik,
        accession=accession,
        form_type=form_type,
    )

    if not force_refresh:
        cached = lookup_cache(resolution)
        if cached is not None:
            _sync_manifest_resolution(cached.local_path, resolution)
            logger.info("cache hit for %s", resolution.accession)
            if not skip_html_narrative:
                from ingestion.html_narrative import ingest_html_for_cache_entry

                ingest_html_for_cache_entry(
                    cached,
                    resolution,
                    skip=False,
                    force_refresh=False,
                )
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
    from ingestion.html_narrative import ingest_html_for_cache_entry

    ingest_html_for_cache_entry(
        entry,
        resolution,
        skip=skip_html_narrative,
        force_refresh=force_refresh,
    )
    return entry


from ingestion.corpus import (  # noqa: E402
    CorpusCapExceededError,
    default_corpus_definition,
    materialize_corpus_members,
    resolve_corpus_members,
)


def start_fetch_job(ident: IssuerIdentifierInput, form_type: str = "10-K") -> FetchJob:
    job_id = f"fetch-{ident.ticker or ident.cik or ident.accession}"
    try:
        resolution = resolve_from_input(ident, form_type=form_type)
        return FetchJob(job_id=job_id, status=FetchJobStatus.PENDING, resolution=resolution)
    except Exception as exc:
        return FetchJob(job_id=job_id, status=FetchJobStatus.FAILED, error=str(exc))
