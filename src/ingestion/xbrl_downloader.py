"""Download XBRL instance and taxonomy artifacts."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ingestion.sec_client import get_sec_client, with_retry
from ingestion.settings import is_mock_mode
from models.ingestion import FilingResolution, XBRLArtifact, XBRLArtifactManifest, XBRLArtifactRole

logger = logging.getLogger(__name__)

_MOCK_HTML_FIXTURE = Path("tests/fixtures/sample_10k.html")


def _mock_artifacts(resolution: FilingResolution) -> list[XBRLArtifact]:
    base = resolution.accession.replace("-", "")
    return [
        XBRLArtifact(
            filename="filing.html",
            role=XBRLArtifactRole.FILING_HTML,
            url="mock://filing_html",
        ),
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
    html_body = (
        _MOCK_HTML_FIXTURE.read_text()
        if _MOCK_HTML_FIXTURE.exists()
        else "<html><body><h1>Mock filing</h1></body></html>"
    )
    # Pad so mock packages pass the same size checks as live filing HTML downloads.
    while len(html_body) < 5_500:
        html_body += (
            "<p>Revenue increased due to strong product demand and services growth.</p>"
            "<table><tr><td>Net sales</td><td>100</td></tr></table>"
        )
    for art in artifacts:
        path = dest / art.filename
        if art.role == XBRLArtifactRole.FILING_HTML:
            path.write_text(html_body)
        elif art.role == XBRLArtifactRole.INSTANCE:
            path.write_text(
                '<?xml version="1.0"?><xbrl xmlns="http://www.xbrl.org/2003/instance">'
                "<context id='c1'/><unit id='u1'/>"
                "<dei:DocumentType contextRef='c1'>10-K</dei:DocumentType>"
                "</xbrl>"
            )
        else:
            path.write_text('<?xml version="1.0"?><schema xmlns="http://www.w3.org/2001/XMLSchema"/>')


def _download_filing_html(resolution: FilingResolution, dest: Path) -> XBRLArtifact | None:
    url = resolution.filing_document_url or resolution.sec_api_filing_url
    if not url or not url.startswith("http"):
        logger.warning("No filing HTML URL for %s", resolution.accession)
        return None

    client = get_sec_client()
    assert client is not None
    render = client["render"]

    def _fetch():
        return render.get_filing(url)

    content = with_retry(_fetch)
    path = dest / "filing.html"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(str(content))

    if path.stat().st_size < 500:
        logger.warning("Filing HTML download too small for %s", resolution.accession)
        return None

    size = path.stat().st_size
    logger.info("Downloaded filing HTML (%s bytes) for %s", size, resolution.accession)
    return XBRLArtifact(
        filename="filing.html",
        role=XBRLArtifactRole.FILING_HTML,
        url=url,
    )


def list_xbrl_artifacts(resolution: FilingResolution) -> list[XBRLArtifact]:
    if is_mock_mode():
        return _mock_artifacts(resolution)

    client = get_sec_client()
    assert client is not None
    xbrl_api = client["xbrl"]

    def _fetch():
        return xbrl_api.xbrl_to_json(
            htm_url=resolution.filing_document_url or resolution.sec_api_filing_url or None,
            accession_no=resolution.accession,
        )

    artifacts: list[XBRLArtifact] = []
    try:
        data = with_retry(_fetch)
        if isinstance(data, dict):
            for key, url in (data.get("instance") or {}).items():
                if isinstance(url, str) and url.startswith("http"):
                    artifacts.append(
                        XBRLArtifact(
                            filename=Path(url).name or f"{key}.xml",
                            role=XBRLArtifactRole.INSTANCE,
                            url=url,
                        )
                    )
    except Exception as exc:
        logger.warning("XBRL artifact listing failed for %s: %s", resolution.accession, exc)

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

    if is_mock_mode():
        arts = artifacts or _mock_artifacts(resolution)
        _mock_write_files(dest, arts)
    else:
        import httpx

        arts: list[XBRLArtifact] = []
        html_art = _download_filing_html(resolution, dest)
        if html_art is not None:
            arts.append(html_art)

        for art in artifacts or list_xbrl_artifacts(resolution):
            if art.role == XBRLArtifactRole.FILING_HTML:
                continue
            path = dest / art.filename
            if art.url and art.url.startswith("http"):
                resp = httpx.get(art.url, timeout=120.0)
                resp.raise_for_status()
                path.write_bytes(resp.content)
            elif not path.exists():
                path.write_text(f"<!-- placeholder for {art.role} -->")
            arts.append(art)

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
    from ingestion.settings import get_settings

    root = get_settings().sec_downloads_root
    return root / resolution.ticker.upper() / resolution.accession
