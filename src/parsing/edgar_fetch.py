"""EDGAR filing download helpers."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import httpx

from models.filing import FilingRef

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
USER_AGENT = "agentic-graphrag-finance research@example.com"


def normalize_cik(cik: str) -> str:
    return cik.strip().lstrip("0").zfill(10)


def accession_no_dashes(accession: str) -> str:
    return accession.replace("-", "")


def build_filing_uri(cik: str, accession: str, primary_doc: str = "") -> str:
    cik_num = normalize_cik(cik).lstrip("0")
    acc = accession_no_dashes(accession)
    base = f"{SEC_ARCHIVES}/{cik_num}/{acc}"
    if primary_doc:
        return f"{base}/{primary_doc}"
    return base


def download_filing(
    filing: FilingRef,
    dest_dir: Path,
    *,
    client: httpx.Client | None = None,
) -> Path:
    """Download primary filing HTML to dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    uri = filing.source_uri or build_filing_uri(filing.cik, filing.accession)
    out_path = dest_dir / f"{filing.accession}.html"
    owns_client = client is None
    http = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0)
    try:
        resp = http.get(uri)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
    finally:
        if owns_client:
            http.close()
    return out_path


def parse_filing_metadata_from_path(path: Path, cik: str, form_type: str) -> FilingRef:
    """Build FilingRef from local file when EDGAR index is unavailable."""
    acc_match = re.search(r"(\d{10}-\d{2}-\d{6})", path.stem)
    accession = acc_match.group(1) if acc_match else path.stem
    today = date.today()
    return FilingRef(
        cik=normalize_cik(cik),
        accession=accession,
        form_type=form_type,
        filed_at=today,
        period_end=today,
        source_uri=str(path),
    )
