"""Download full XBRL packages from SEC EDGAR (free, no API key).

Uses the public EDGAR filing ``index.json`` and ``*-xbrl.zip`` artifacts.
See specs/002-live-disclosure-cli/research-xbrl-retrieval.md.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path

import httpx

from models.ingestion import FilingResolution, XBRLArtifact, XBRLArtifactRole

logger = logging.getLogger(__name__)

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_USER_AGENT = "agentic-graphrag-finance contact@example.com"

_XBRL_LINKBASE_SUFFIXES = {
    "_cal.xml": XBRLArtifactRole.CALCULATION,
    "_def.xml": XBRLArtifactRole.DEFINITION,
    "_lab.xml": XBRLArtifactRole.LABEL,
    "_pre.xml": XBRLArtifactRole.PRESENTATION,
}


def edgar_user_agent() -> str:
    return os.environ.get("SEC_EDGAR_USER_AGENT", DEFAULT_USER_AGENT)


def _cik_path(cik: str) -> str:
    return cik.strip().lstrip("0") or "0"


def _accession_path(accession: str) -> str:
    return accession.replace("-", "")


def edgar_index_url(cik: str, accession: str) -> str:
    return f"{SEC_ARCHIVES}/{_cik_path(cik)}/{_accession_path(accession)}/index.json"


def edgar_file_url(cik: str, accession: str, filename: str) -> str:
    return f"{SEC_ARCHIVES}/{_cik_path(cik)}/{_accession_path(accession)}/{filename}"


def classify_filename(name: str) -> XBRLArtifactRole:
    lower = name.lower()
    if lower.endswith("-xbrl.zip") or lower.endswith("_xbrl.zip"):
        return XBRLArtifactRole.XBRL_ZIP
    if lower.endswith("_htm.xml") or (lower.endswith(".xml") and "htm" in lower):
        return XBRLArtifactRole.INSTANCE
    if lower.endswith(".xsd"):
        return XBRLArtifactRole.SCHEMA
    for suffix, role in _XBRL_LINKBASE_SUFFIXES.items():
        if lower.endswith(suffix):
            return role
    if lower.endswith(".xml"):
        return XBRLArtifactRole.OTHER
    return XBRLArtifactRole.OTHER


def is_xbrl_package_file(name: str) -> bool:
    role = classify_filename(name)
    return role in {
        XBRLArtifactRole.XBRL_ZIP,
        XBRLArtifactRole.INSTANCE,
        XBRLArtifactRole.SCHEMA,
        XBRLArtifactRole.CALCULATION,
        XBRLArtifactRole.DEFINITION,
        XBRLArtifactRole.LABEL,
        XBRLArtifactRole.PRESENTATION,
        XBRLArtifactRole.OTHER,
    } and (
        name.lower().endswith((".xml", ".xsd", ".zip"))
        or "-xbrl.zip" in name.lower()
    )


def fetch_edgar_index(
    resolution: FilingResolution,
    *,
    client: httpx.Client | None = None,
) -> list[str]:
    """Return filenames listed in the filing's EDGAR index.json."""
    url = edgar_index_url(resolution.cik, resolution.accession)
    owns = client is None
    http = client or httpx.Client(
        headers={"User-Agent": edgar_user_agent(), "Accept": "application/json"},
        timeout=60.0,
    )
    try:
        resp = http.get(url)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns:
            http.close()
    items = data.get("directory", {}).get("item", [])
    names: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _download_file(
    url: str,
    dest: Path,
    *,
    client: httpx.Client,
) -> None:
    resp = client.get(url)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)


def _extract_xbrl_zip(zip_path: Path, dest: Path) -> list[str]:
    extracted: list[str] = []
    xbrl_dir = dest / "xbrl_extracted"
    xbrl_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            name = Path(member).name
            if not is_xbrl_package_file(name):
                continue
            if name.lower().endswith(".htm") and "_htm.xml" not in name.lower():
                continue
            target = xbrl_dir / name
            target.write_bytes(zf.read(member))
            extracted.append(str(target.relative_to(dest)))
    return extracted


def download_edgar_xbrl_package(
    resolution: FilingResolution,
    dest: Path,
    *,
    client: httpx.Client | None = None,
) -> list[XBRLArtifact]:
    """Download full XBRL instance + linkbases (and optional zip) from EDGAR."""
    dest.mkdir(parents=True, exist_ok=True)
    owns = client is None
    http = client or httpx.Client(
        headers={"User-Agent": edgar_user_agent()},
        timeout=120.0,
    )
    artifacts: list[XBRLArtifact] = []

    try:
        names = fetch_edgar_index(resolution, client=http)
        xbrl_names = [n for n in names if is_xbrl_package_file(n)]

        zip_names = [n for n in xbrl_names if classify_filename(n) == XBRLArtifactRole.XBRL_ZIP]
        if zip_names:
            zip_name = zip_names[0]
            zip_url = edgar_file_url(resolution.cik, resolution.accession, zip_name)
            zip_path = dest / zip_name
            _download_file(zip_url, zip_path, client=http)
            artifacts.append(
                XBRLArtifact(
                    filename=zip_name,
                    role=XBRLArtifactRole.XBRL_ZIP,
                    url=zip_url,
                )
            )
            for rel in _extract_xbrl_zip(zip_path, dest):
                path = dest / rel
                artifacts.append(
                    XBRLArtifact(
                        filename=rel,
                        role=classify_filename(path.name),
                        url=edgar_file_url(resolution.cik, resolution.accession, path.name),
                    )
                )

        # Always fetch loose instance + taxonomy files (some filings omit zip or zip is incomplete).
        for name in xbrl_names:
            if name in zip_names:
                continue
            out = dest / name
            if out.exists() and out.stat().st_size > 0:
                continue
            url = edgar_file_url(resolution.cik, resolution.accession, name)
            _download_file(url, out, client=http)
            artifacts.append(
                XBRLArtifact(filename=name, role=classify_filename(name), url=url)
            )
            time.sleep(0.12)  # stay under SEC 10 req/s fair-access guidance

    finally:
        if owns:
            http.close()

    if not artifacts:
        raise RuntimeError(
            f"No XBRL artifacts found in EDGAR index for {resolution.accession}"
        )

    logger.info(
        "EDGAR XBRL package: %s files for %s (%s)",
        len(artifacts),
        resolution.accession,
        resolution.ticker,
    )
    return artifacts
