"""Filing accession metadata catalog for benchmark sampling (CLI layer)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ingestion.edgar_client import list_recent_filings, resolve_ticker
from models.benchmark_generation import (
    AccessionRecord,
    GenerationConfig,
    IssuerAllowlist,
)


def _fiscal_year(period_end: date) -> int:
    return period_end.year


def _load_fixture_catalog(ticker: str, root: Path) -> list[AccessionRecord]:
    base = root / "tests/fixtures/sec_downloads" / ticker.upper()
    if not base.is_dir():
        return []
    records: list[AccessionRecord] = []
    for acc_dir in sorted(base.iterdir()):
        manifest_path = acc_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        resolution = data.get("resolution", {})
        period = resolution.get("period_end", resolution.get("filed_at", "2024-01-01"))[:10]
        period_date = date.fromisoformat(period)
        records.append(
            AccessionRecord(
                accession=str(resolution.get("accession", acc_dir.name)),
                form_type=str(resolution.get("form_type", "10-K")),
                fiscal_year=_fiscal_year(period_date),
                filed_at=str(resolution.get("filed_at", period))[:10],
            )
        )
    return records


def build_accession_catalog(
    config: GenerationConfig,
    allowlist: IssuerAllowlist,
    *,
    repo_root: Path | None = None,
    prefer_fixtures: bool = False,
) -> dict[str, list[AccessionRecord]]:
    """Build ticker → accession list for sampling (EDGAR or fixture fallback)."""
    root = repo_root or Path(__file__).resolve().parents[2]
    catalog: dict[str, list[AccessionRecord]] = {}
    filters = config.filing_filters
    for entry in allowlist.entries:
        ticker = entry.ticker.upper()
        fixture_rows = _load_fixture_catalog(ticker, root)
        if fixture_rows and (prefer_fixtures or config.config_id == "custom_judge_ci"):
            catalog[ticker] = fixture_rows
            continue
        try:
            cik = entry.cik or resolve_ticker(ticker)
            resolutions = list_recent_filings(
                cik=cik,
                ticker=ticker,
                form_types=filters.form_types,
                max_per_form=filters.max_filings_per_issuer,
            )
        except Exception:
            catalog[ticker] = fixture_rows
            continue
        catalog[ticker] = [
            AccessionRecord(
                accession=r.accession,
                form_type=r.form_type,
                fiscal_year=_fiscal_year(r.period_end),
                filed_at=r.filed_at.isoformat(),
            )
            for r in resolutions
        ]
    return catalog
