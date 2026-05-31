"""Supplementary HTML narrative ingest for XBRL-complete cache packages."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from ingestion.edgar_http import edgar_headers, with_edgar_retry
from ingestion.edgar_xbrl import (
    edgar_file_url,
    fetch_edgar_index,
    is_xbrl_package_file,
)
from ingestion.package_utils import find_narrative_html_candidate, xbrl_package_is_complete
from ingestion.validators import ValidationError
from ingestion.xbrl_downloader import write_manifest
from models.enums import HtmlNarrativeStatus
from models.ingestion import (
    CacheEntry,
    FilingResolution,
    XBRLArtifact,
    XBRLArtifactManifest,
    XBRLArtifactRole,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupplementaryHtmlResolution:
    path: Path
    role: str
    suitable: bool


def load_html_narrative_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/html_narrative.yaml")
    if not path.exists():
        return {"html_narrative_enabled": True, "min_html_bytes": 5000}
    return yaml.safe_load(path.read_text()) or {}


def resolve_narrative_html(
    package_root: Path,
    manifest: XBRLArtifactManifest,
) -> SupplementaryHtmlResolution | None:
    """Prefer inline/iXBRL HTML in package; None if no candidate."""
    cfg = load_html_narrative_config()
    min_bytes = int(cfg.get("min_html_bytes", 5000))
    candidate = find_narrative_html_candidate(package_root, manifest, min_bytes=min_bytes)
    if candidate is not None:
        return SupplementaryHtmlResolution(path=candidate, role="inline_ixbrl", suitable=True)
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.FILING_HTML:
            path = package_root / art.filename
            if path.is_file() and path.stat().st_size >= min_bytes:
                return SupplementaryHtmlResolution(path=path, role="filing_htm", suitable=True)
    return None


def _pick_primary_htm_filename(names: list[str]) -> str | None:
    """Choose main filing .htm (e.g. aapl-20250927.htm), not exhibits or R1.htm tables."""
    candidates: list[str] = []
    for name in names:
        lower = name.lower()
        if not lower.endswith(".htm") or "_htm.xml" in lower:
            continue
        if lower.startswith("a10-k") or re.match(r"^r\d+\.htm$", lower):
            continue
        candidates.append(name)
    if not candidates:
        return None
    main_doc = [
        n
        for n in candidates
        if re.search(r"-\d{8}\.htm$", n.lower()) and "exhibit" not in n.lower()
    ]
    if main_doc:
        return sorted(main_doc, key=len, reverse=True)[0]
    return max(candidates, key=len)


def _download_primary_htm(resolution: FilingResolution, dest: Path) -> Path | None:
    names = fetch_edgar_index(resolution)
    primary = _pick_primary_htm_filename(names)
    if not primary:
        return None
    url = edgar_file_url(resolution.cik, resolution.accession, primary)
    out = dest / primary
    with httpx.Client(headers=edgar_headers(), timeout=120.0) as client:

        def _fetch() -> None:
            resp = client.get(url)
            resp.raise_for_status()
            out.write_bytes(resp.content)

        with_edgar_retry(_fetch)
    return out


def _update_manifest_html(
    package_root: Path,
    manifest: XBRLArtifactManifest,
    *,
    status: HtmlNarrativeStatus,
    role: str = "",
    relpath: str = "",
    extra_artifact: XBRLArtifact | None = None,
) -> XBRLArtifactManifest:
    artifacts = list(manifest.artifacts)
    if extra_artifact and extra_artifact.filename not in {a.filename for a in artifacts}:
        artifacts.append(extra_artifact)
    updated = manifest.model_copy(
        update={
            "artifacts": artifacts,
            "html_narrative_status": status.value,
            "html_artifact_role": role,
            "html_artifact_relpath": relpath,
        }
    )
    write_manifest(package_root, updated)
    return updated


def ingest_html_narrative(
    resolution: FilingResolution,
    package_root: Path,
    *,
    skip: bool = False,
    force_refresh: bool = False,
) -> HtmlNarrativeStatus:
    """Supplementary HTML for a cached XBRL package (FR-001)."""
    manifest_path = package_root / "manifest.json"
    if not manifest_path.exists():
        raise ValidationError("Cannot ingest HTML without XBRL manifest")
    manifest = XBRLArtifactManifest.model_validate_json(manifest_path.read_text())
    if not xbrl_package_is_complete(package_root, manifest):
        raise ValidationError("Cannot ingest HTML narrative without complete XBRL package")

    if skip:
        _update_manifest_html(package_root, manifest, status=HtmlNarrativeStatus.SKIPPED)
        return HtmlNarrativeStatus.SKIPPED

    if (
        manifest.html_narrative_status == HtmlNarrativeStatus.SUCCESS.value
        and not force_refresh
    ):
        rel = manifest.html_artifact_relpath
        if rel and (package_root / rel).exists():
            return HtmlNarrativeStatus.SUCCESS

    resolved = resolve_narrative_html(package_root, manifest)
    needs_htm = (
        resolved is None
        or not resolved.suitable
        or (
            resolved.role == "inline_ixbrl"
            and resolution.form_type.upper() == "10-K"
        )
    )
    if needs_htm:
        fallback: Path | None = None
        try:
            fallback = _download_primary_htm(resolution, package_root)
        except Exception as exc:
            logger.warning("HTML fallback download failed for %s: %s", resolution.accession, exc)
        if fallback is not None:
            rel = str(fallback.relative_to(package_root))
            extra = XBRLArtifact(
                filename=rel,
                role=XBRLArtifactRole.FILING_HTML,
                url=edgar_file_url(resolution.cik, resolution.accession, fallback.name),
            )
            _update_manifest_html(
                package_root,
                manifest,
                status=HtmlNarrativeStatus.SUCCESS,
                role="filing_htm_fallback",
                relpath=rel,
                extra_artifact=extra,
            )
            return HtmlNarrativeStatus.SUCCESS
        if resolved is None or not resolved.suitable:
            _update_manifest_html(package_root, manifest, status=HtmlNarrativeStatus.FAILED)
            return HtmlNarrativeStatus.FAILED

    if resolved is None:
        _update_manifest_html(package_root, manifest, status=HtmlNarrativeStatus.FAILED)
        return HtmlNarrativeStatus.FAILED

    rel = str(resolved.path.relative_to(package_root))
    _update_manifest_html(
        package_root,
        manifest,
        status=HtmlNarrativeStatus.SUCCESS,
        role=resolved.role,
        relpath=rel,
    )
    return HtmlNarrativeStatus.SUCCESS


def ingest_html_for_cache_entry(
    entry: CacheEntry,
    resolution: FilingResolution,
    *,
    skip: bool = False,
    force_refresh: bool = False,
) -> HtmlNarrativeStatus:
    return ingest_html_narrative(
        resolution,
        entry.local_path,
        skip=skip,
        force_refresh=force_refresh,
    )


def assert_not_html_only_package(package_root: Path) -> None:
    """Reject orphan HTML-only cache directories (FR-001)."""
    manifest_path = package_root / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = XBRLArtifactManifest.model_validate_json(manifest_path.read_text())
    if xbrl_package_is_complete(package_root, manifest):
        return
    has_html = any(
        a.role == XBRLArtifactRole.FILING_HTML for a in manifest.artifacts
    ) or any(package_root.glob("*.htm"))
    has_xbrl = any(is_xbrl_package_file(a.filename) for a in manifest.artifacts)
    if has_html and not has_xbrl:
        raise ValidationError("HTML-only cache entries are not permitted without XBRL package")
