"""Download XBRL instance and taxonomy artifacts."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ingestion.sec_client import get_sec_client, with_retry
from ingestion.settings import get_settings, is_mock_mode
from models.ingestion import FilingResolution, XBRLArtifact, XBRLArtifactManifest, XBRLArtifactRole

logger = logging.getLogger(__name__)


def _mock_artifacts(resolution: FilingResolution) -> list[XBRLArtifact]:
    base = resolution.accession.replace("-", "")
    return [
        XBRLArtifact(
            filename=f"{base}_htm.xml",
            role=XBRLArtifactRole.INSTANCE,
            url="mock://instance",
        ),
        XBRLArtifact(
            filename=f"{base}.xsd",
            role=XBRLArtifactRole.SCHEMA,
            url="mock://schema",
        ),
    ]


def _mock_write_files(dest: Path, artifacts: list[XBRLArtifact]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for art in artifacts:
        path = dest / art.filename
        if art.role == XBRLArtifactRole.INSTANCE:
            path.write_text(
                '<?xml version="1.0"?><xbrl xmlns="http://www.xbrl.org/2003/instance">'
                "<context id='c1'/><unit id='u1'/>"
                "<dei:DocumentType contextRef='c1'>10-K</dei:DocumentType>"
                "</xbrl>"
            )
        else:
            path.write_text('<?xml version="1.0"?><schema xmlns="http://www.w3.org/2001/XMLSchema"/>')


def list_xbrl_artifacts(resolution: FilingResolution) -> list[XBRLArtifact]:
    if is_mock_mode():
        return _mock_artifacts(resolution)

    client = get_sec_client()
    assert client is not None
    xbrl_api = client["xbrl"]

    def _fetch():
        return xbrl_api.xbrl_to_json(
            htm_url=resolution.sec_api_filing_url or None,
            accession_no=resolution.accession,
        )

    data = with_retry(_fetch)
    artifacts: list[XBRLArtifact] = []
    if isinstance(data, dict):
        for key, url in (data.get("instance") or {}).items():
            if isinstance(url, str):
                artifacts.append(
                    XBRLArtifact(
                        filename=Path(url).name or f"{key}.xml",
                        role=XBRLArtifactRole.INSTANCE,
                        url=url,
                    )
                )
    if not artifacts:
        acc = resolution.accession.replace("-", "")
        artifacts = [
            XBRLArtifact(filename=f"{acc}.xml", role=XBRLArtifactRole.INSTANCE, url=""),
            XBRLArtifact(filename=f"{acc}.xsd", role=XBRLArtifactRole.SCHEMA, url=""),
        ]
    return artifacts


def download_artifacts(
    resolution: FilingResolution,
    dest: Path,
    artifacts: list[XBRLArtifact] | None = None,
) -> XBRLArtifactManifest:
    dest.mkdir(parents=True, exist_ok=True)
    arts = artifacts or list_xbrl_artifacts(resolution)

    if is_mock_mode():
        _mock_write_files(dest, arts)
    else:
        import httpx

        for art in arts:
            path = dest / art.filename
            if art.url and art.url.startswith("http"):
                resp = httpx.get(art.url, timeout=120.0)
                resp.raise_for_status()
                path.write_bytes(resp.content)
            elif not path.exists():
                path.write_text(f"<!-- placeholder for {art.role} -->")

    updated: list[XBRLArtifact] = []
    for art in arts:
        path = dest / art.filename
        h = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        updated.append(art.model_copy(update={"content_hash": h}))

    manifest = XBRLArtifactManifest(resolution=resolution, artifacts=updated, complete=False)
    return manifest


def write_manifest(dest: Path, manifest: XBRLArtifactManifest) -> Path:
    path = dest / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def package_dir(resolution: FilingResolution) -> Path:
    root = get_settings().sec_downloads_root
    return root / resolution.ticker.upper() / resolution.accession
