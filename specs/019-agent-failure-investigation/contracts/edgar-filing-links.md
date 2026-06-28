# Contract: SEC EDGAR Filing Links in Investigation Views

**Feature**: 019 | **Module**: `evaluation/reproduction/investigation/edgar_links.py`

## URL format

Human-readable filing index page:

```text
https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_no_dashes}/{accession}-index.htm
```

Example:

- CIK `0000320193`, accession `0000320193-25-000079`
- URL `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm`

## CIK resolution order

1. Bundle snapshot manifest `filing_refs[].cik` for accession
2. Bundle issuer index sidecar if present
3. Fail closed: emit `EdgarFilingLink` with `link_omitted_reason: missing_cik`

## Display rules

- Investigation pack shows link text: `{form_type} {period_end} — {accession}` (clickable when url present)
- Repro drill-down uses same builder
- Offline export: URLs are static strings (no live EDGAR fetch at view time)

## Tests

- `tests/unit/test_edgar_links.py` — AAPL/XOM accessions from bundle fixtures; missing CIK case
