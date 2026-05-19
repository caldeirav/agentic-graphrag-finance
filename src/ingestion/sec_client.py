"""SEC identifier resolution and filing lookup via sec-api."""

from __future__ import annotations

import json
import logging
import time
from datetime import date

from ingestion.settings import get_settings, is_mock_mode, require_sec_api_key
from models.ingestion import FilingResolution, IssuerIdentifierInput

logger = logging.getLogger(__name__)

_DEFAULT_TICKERS: dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
}


class ResolutionError(LookupError):
    """Failed to resolve issuer or filing."""


def _normalize_cik(cik: str) -> str:
    return cik.strip().lstrip("0").zfill(10)


def _load_ticker_map() -> dict[str, str]:
    path = get_settings().ticker_map_cache
    if path.exists():
        data = json.loads(path.read_text())
        return {k.upper(): v for k, v in data.items()}
    return dict(_DEFAULT_TICKERS)


def _save_ticker_map(mapping: dict[str, str]) -> None:
    path = get_settings().ticker_map_cache
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2))


def resolve_ticker(ticker: str) -> str:
    mapping = _load_ticker_map()
    key = ticker.upper().strip()
    if key not in mapping:
        if is_mock_mode():
            raise ResolutionError(f"Unknown ticker in mock mode: {ticker}")
        mapping = _resolve_ticker_via_api(key, mapping)
    return _normalize_cik(mapping[key])


def _resolve_ticker_via_api(ticker: str, mapping: dict[str, str]) -> dict[str, str]:
    from sec_api import MappingApi

    api = MappingApi(require_sec_api_key())
    result = api.resolve(ticker)
    if not result:
        raise ResolutionError(f"Could not resolve ticker: {ticker}")
    cik = _normalize_cik(str(result.get("cik", result) if isinstance(result, dict) else result))
    mapping[ticker] = cik
    _save_ticker_map(mapping)
    return mapping


def _mock_resolution(
    *,
    ticker: str,
    cik: str,
    accession: str,
    form_type: str,
) -> FilingResolution:
    today = date.today()
    return FilingResolution(
        ticker=ticker.upper(),
        cik=cik,
        accession=accession,
        form_type=form_type,
        filed_at=today,
        period_end=today,
        sec_api_filing_url=f"https://sec.gov/mock/{accession}",
    )


def _query_latest_filing(cik: str, form_type: str) -> FilingResolution:
    if is_mock_mode():
        ticker = next((t for t, c in _load_ticker_map().items() if c == cik), "MOCK")
        return _mock_resolution(
            ticker=ticker,
            cik=cik,
            accession="0000320193-24-000123",
            form_type=form_type,
        )

    from sec_api import QueryApi

    query = (
        f'cik:{cik.lstrip("0")} AND formType:"{form_type}" '
        f"AND NOT formType:(\"NT 10-K\" OR \"NT 10-Q\")"
    )
    api = QueryApi(require_sec_api_key())
    filings = api.get_filings({"query": {"query_string": {"query": query}}, "size": "1"})
    if not filings or not filings.get("filings"):
        raise ResolutionError(f"No {form_type} filing found for CIK {cik}")
    f = filings["filings"][0]
    ticker = f.get("ticker", "UNKNOWN").upper()
    return FilingResolution(
        ticker=ticker,
        cik=_normalize_cik(str(f.get("cik", cik))),
        accession=f["accessionNo"],
        form_type=f.get("formType", form_type),
        filed_at=date.fromisoformat(f["filedAt"][:10]),
        period_end=date.fromisoformat(f.get("periodOfReport", f["filedAt"])[:10]),
        sec_api_filing_url=f.get("linkToFilingDetails", ""),
        filing_document_url=f.get("linkToHtml", "") or f.get("linkToFilingDetails", ""),
    )


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
        if resolved_cik != _normalize_cik(cik):
            raise ResolutionError(
                f"Ticker {ticker} maps to CIK {resolved_cik}, but CIK {cik} was provided"
            )

    if accession:
        use_cik = _normalize_cik(cik) if cik else (resolve_ticker(ticker) if ticker else "")
        use_ticker = ticker.upper() if ticker else "UNKNOWN"
        if is_mock_mode():
            return _mock_resolution(
                ticker=use_ticker,
                cik=use_cik or "0000000000",
                accession=accession,
                form_type=form_type,
            )
        return FilingResolution(
            ticker=use_ticker,
            cik=use_cik,
            accession=accession,
            form_type=form_type,
            filed_at=date.today(),
            period_end=date.today(),
            sec_api_filing_url=f"https://www.sec.gov/cgi-bin/viewer?action=view&accn={accession}",
        )

    use_cik = _normalize_cik(cik) if cik else resolve_ticker(ticker or "")
    _throttle()
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


def get_sec_client():
    """Return sec-api handle for downstream download modules."""
    require_sec_api_key()
    if is_mock_mode():
        return None
    from sec_api import QueryApi, RenderApi, XbrlApi

    key = require_sec_api_key()
    return {"query": QueryApi(key), "xbrl": XbrlApi(key), "render": RenderApi(key)}


_last_request = 0.0


def _throttle() -> None:
    global _last_request
    settings = get_settings()
    min_interval = 1.0 / max(settings.sec_api_requests_per_second, 0.1)
    now = time.time()
    elapsed = now - _last_request
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request = time.time()


def with_retry(func, *, max_attempts: int = 3):
    """Retry helper for sec-api 429/5xx (T046)."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "429" in msg or "500" in msg or "502" in msg or "503" in msg:
                logger.warning("sec-api retry %s/%s: %s", attempt + 1, max_attempts, exc)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise last_exc  # type: ignore[misc]
