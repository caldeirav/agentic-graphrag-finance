"""SEC EDGAR filing link builder for investigation views (019)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from models.investigation import EdgarFilingLink


def _normalize_cik(cik: str) -> str:
    return str(cik).lstrip("0") or "0"


def _accession_no_dashes(accession: str) -> str:
    return accession.replace("-", "")


def build_edgar_url(cik: str, accession: str) -> str:
    cik_int = _normalize_cik(cik)
    acc_nodash = _accession_no_dashes(accession)
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{acc_nodash}/{accession}-index.htm"
    )


def _load_filing_ref_index(bundle_root: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    graphs_dir = bundle_root / "corpus" / "graphs"
    if not graphs_dir.is_dir():
        return index
    for manifest_path in graphs_dir.glob("**/*.manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for ref in payload.get("filing_refs") or []:
            accession = str(ref.get("accession") or "").strip()
            if accession:
                index[accession] = ref
    issuer_index = bundle_root / "corpus" / "issuer_index.json"
    if issuer_index.is_file():
        try:
            payload = json.loads(issuer_index.read_text(encoding="utf-8"))
            for entry in payload.get("filings") or []:
                accession = str(entry.get("accession") or "").strip()
                if accession and accession not in index:
                    index[accession] = entry
        except (OSError, json.JSONDecodeError):
            pass
    return index


def _parse_period_end(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def build_edgar_links(
    bundle_root: Path,
    accessions: list[str],
    *,
    form_types: dict[str, str] | None = None,
) -> list[EdgarFilingLink]:
    filing_index = _load_filing_ref_index(bundle_root)
    form_types = form_types or {}
    links: list[EdgarFilingLink] = []
    for accession in accessions:
        ref = filing_index.get(accession, {})
        cik = str(ref.get("cik") or "").strip()
        form_type = str(ref.get("form_type") or form_types.get(accession, "")).strip()
        period_end = _parse_period_end(ref.get("period_end"))
        if cik:
            links.append(
                EdgarFilingLink(
                    accession=accession,
                    form_type=form_type,
                    period_end=period_end,
                    url=build_edgar_url(cik, accession),
                )
            )
        else:
            links.append(
                EdgarFilingLink(
                    accession=accession,
                    form_type=form_type,
                    period_end=period_end,
                    link_omitted_reason="missing_cik",
                )
            )
    return links
