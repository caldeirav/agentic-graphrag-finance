"""SEC EDGAR identifier resolution and latest-filing lookup (no third-party API keys)."""

from __future__ import annotations

import json
import logging
import time
from datetime import date

import httpx

from ingestion.edgar_xbrl import edgar_user_agent
from ingestion.settings import get_settings, is_fixture_ingestion, require_edgar_user_agent
from models.ingestion import FilingResolution, IssuerIdentifierInput

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_DEFAULT_TICKERS: dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
}

_FIXTURE_ACCESSION = "0000320193-24-000123"
_FIXTURE_TICKER = "AAPL"
_FIXTURE_CIK = "0000320193"


class ResolutionError(LookupError):
    """Failed to resolve issuer or filing."""


def normalize_cik(cik: str) -> str:
    return cik.strip().lstrip("0").zfill(10)


def _load_ticker_map() -> dict[str, str]:
    path = get_settings().ticker_map_cache
    if path.exists():
        data = json.loads(path.read_text())
        return {k.upper(): normalize_cik(v) for k, v in data.items()}
    return {k: normalize_cik(v) for k, v in _DEFAULT_TICKERS.items()}


def _save_ticker_map(mapping: dict[str, str]) -> None:
    path = get_settings().ticker_map_cache
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2))


def _edgar_headers() -> dict[str, str]:
    require_edgar_user_agent()
    return {"User-Agent": edgar_user_agent(), "Accept": "application/json"}


def with_retry(func, *, max_attempts: int = 3):
    """Retry EDGAR HTTP calls on rate-limit and server errors."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in (429, 500, 502, 503, 504):
                logger.warning("EDGAR retry %s/%s: %s", attempt + 1, max_attempts, exc)
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as exc:
            last_exc = exc
            raise
    raise last_exc  # type: ignore[misc]


_last_request = 0.0


def _throttle() -> None:
    global _last_request
    settings = get_settings()
    min_interval = 1.0 / max(settings.edgar_requests_per_second, 0.1)
    now = time.time()
    elapsed = now - _last_request
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request = time.time()


def _fetch_json(url: str) -> dict | list:
    def _get():
        _throttle()
        with httpx.Client(headers=_edgar_headers(), timeout=60.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    return with_retry(_get)


def _resolve_ticker_via_edgar(ticker: str, mapping: dict[str, str]) -> dict[str, str]:
    data = _fetch_json(COMPANY_TICKERS_URL)
    if not isinstance(data, dict):
        raise ResolutionError(f"Unexpected ticker map response for {ticker}")
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("ticker", "")).upper() == ticker:
            mapping[ticker] = normalize_cik(str(entry["cik_str"]))
            _save_ticker_map(mapping)
            return mapping
    raise ResolutionError(f"Could not resolve ticker via EDGAR: {ticker}")


def resolve_ticker(ticker: str) -> str:
    mapping = _load_ticker_map()
    key = ticker.upper().strip()
    if key not in mapping:
        if is_fixture_ingestion():
            raise ResolutionError(f"Unknown ticker in fixture mode: {ticker}")
        mapping = _resolve_ticker_via_edgar(key, mapping)
    return mapping[key]


def _fixture_resolution(
    *,
    ticker: str,
    cik: str,
    accession: str,
    form_type: str,
) -> FilingResolution:
    return FilingResolution(
        ticker=ticker.upper(),
        cik=cik,
        accession=accession,
        form_type=form_type,
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        edgar_filing_url=f"fixture://{_FIXTURE_TICKER}/{accession}",
    )


def _query_latest_filing(cik: str, form_type: str) -> FilingResolution:
    if is_fixture_ingestion():
        ticker = next((t for t, c in _load_ticker_map().items() if c == cik), _FIXTURE_TICKER)
        return _fixture_resolution(
            ticker=ticker,
            cik=cik,
            accession=_FIXTURE_ACCESSION,
            form_type=form_type,
        )

    url = SUBMISSIONS_URL.format(cik=cik)
    data = _fetch_json(url)
    if not isinstance(data, dict):
        raise ResolutionError(f"Invalid submissions payload for CIK {cik}")

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    for i, form in enumerate(forms):
        if form != form_type:
            continue
        accession = accessions[i]
        filed = filed_dates[i] if i < len(filed_dates) else ""
        report = report_dates[i] if i < len(report_dates) else filed
        tickers = data.get("tickers", [])
        ticker = tickers[0].upper() if tickers else "UNKNOWN"
        acc_path = accession.replace("-", "")
        edgar_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_path}/index.json"
        )
        return FilingResolution(
            ticker=ticker,
            cik=cik,
            accession=accession,
            form_type=form_type,
            filed_at=date.fromisoformat(filed[:10]),
            period_end=date.fromisoformat((report or filed)[:10]),
            edgar_filing_url=edgar_url,
        )

    raise ResolutionError(f"No {form_type} filing found for CIK {cik}")


def resolve_identifier(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
    form_type: str = "10-K",
) -> FilingResolution:
    """Resolve to a single filing (latest for form_type when accession omitted)."""
    if ticker and cik:
        resolved_cik = resolve_ticker(ticker)
        if resolved_cik != normalize_cik(cik):
            raise ResolutionError(
                f"Ticker {ticker} maps to CIK {resolved_cik}, but CIK {cik} was provided"
            )

    if accession:
        use_cik = normalize_cik(cik) if cik else (resolve_ticker(ticker) if ticker else "")
        use_ticker = ticker.upper() if ticker else "UNKNOWN"
        if is_fixture_ingestion():
            return _fixture_resolution(
                ticker=use_ticker,
                cik=use_cik or _FIXTURE_CIK,
                accession=accession,
                form_type=form_type,
            )
        acc_path = accession.replace("-", "")
        edgar_url = (
            f"https://www.sec.gov/Archives/edgar/data/{use_cik.lstrip('0')}/{acc_path}/index.json"
        )
        return FilingResolution(
            ticker=use_ticker,
            cik=use_cik,
            accession=accession,
            form_type=form_type,
            filed_at=date.today(),
            period_end=date.today(),
            edgar_filing_url=edgar_url,
        )

    use_cik = normalize_cik(cik) if cik else resolve_ticker(ticker or "")
    return _query_latest_filing(use_cik, form_type)


def resolve_from_input(ident: IssuerIdentifierInput, form_type: str = "10-K") -> FilingResolution:
    if not ident.ticker and not ident.cik and not ident.accession:
        raise ResolutionError("Provide at least one of ticker, cik, or accession")
    return resolve_identifier(
        ticker=ident.ticker,
        cik=ident.cik,
        accession=ident.accession,
        form_type=form_type,
    )
