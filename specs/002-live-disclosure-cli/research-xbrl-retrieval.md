# Research: XBRL-First Retrieval (Canonical Structured Source)

**Date**: 2026-05-19 | **Status**: Adopted | **Plan**: [plan.md](./plan.md)

## Decision

**Primary structured source for graph building is the full SEC XBRL package** (instance document + taxonomy linkbases), downloaded from **EDGAR Archives at no license cost**. Parsing uses **Docling `InputFormat.XML_XBRL` only** (no HTML fallback). Filing resolution uses **SEC EDGAR public APIs** (`company_tickers.json`, `data.sec.gov/submissions`).

## Rationale (Constitution II)

Financial GraphRAG requires:

- Tagged facts with contexts, units, and periods (XBRL instance)
- Presentation / calculation / definition / label linkbases for statement structure
- Table-like numeric relationships that HTML-only parsing loses

## Retrieval matrix

| Method | License / cost | What you get | Role in this project |
|--------|----------------|----------------|----------------------|
| **SEC EDGAR Archives** (`index.json`, `*-xbrl.zip`, `*_htm.xml`, linkbases) | **Free** (SEC fair-access; User-Agent required) | Full raw XBRL package | **Download** (`ingestion/edgar_xbrl.py`) |
| **SEC EDGAR** (`company_tickers.json`, submissions API) | **Free** | CIK, accession, dates | **Resolution** (`ingestion/edgar_client.py`) |
| **data.sec.gov** XBRL APIs (`companyfacts`, `companyconcept`) | **Free** | Normalized JSON facts (aggregated) | Future enrichment / validation |
| **edgartools** (MIT) | Free / OSS | Pythonic XBRL + filings | Alternative client (not required v1) |
| **Arelle** (Apache 2.0) | Free / OSS | XBRL validation (via `docling[xbrl]`) | Docling backend |

## EDGAR download algorithm (implemented)

1. Resolve filing → `FilingResolution` (CIK, accession, form type) via EDGAR submissions.
2. `GET https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/index.json`
3. Prefer `{accession}-xbrl.zip` → extract XML/XSD into package dir.
4. Also download loose files: `*_htm.xml` (instance), `*.xsd`, `*_cal.xml`, `*_def.xml`, `*_lab.xml`, `*_pre.xml`.
5. Record all files in `XBRLArtifactManifest` with roles (`instance`, `schema`, `calculation`, …).

**Fair access**: set `SEC_EDGAR_USER_AGENT` in `.env` (name + email). Throttle via `EDGAR_REQUESTS_PER_SECOND`.

## Parsing (mandatory Docling)

1. **Docling** `XML_XBRL` on **largest `*_htm.xml` instance** with local taxonomy dir (`src/parsing/docling_xbrl.py`).
2. Extract text blocks, tables, and numeric facts (`key_value_items` → fact table).
3. **No HTML fallback** — failed XBRL conversion raises `ParseError`.

## Package layout (after fetch)

```text
data/raw/sec_downloads/{TICKER}/{accession}/
  manifest.json
  {accession}-xbrl.zip          # optional; extracted under xbrl_extracted/
  xbrl_extracted/
    *_htm.xml                   # primary instance (often 1MB+)
    *.xsd, *_cal.xml, *_def.xml, *_lab.xml, *_pre.xml
```

## Anti-patterns (do not ship)

- HTML-only ingestion or HTML fallback parsing for agent benchmarks.
- Caching fixture stub XML when running live EDGAR (`USE_FIXTURE_INGESTION=0`).
- Preferring narrative HTML over XBRL instance for graph materialization.

## Verification

```bash
ls -la data/raw/sec_downloads/AAPL/*/xbrl_extracted/*_htm.xml
uv run agent-query ask --ticker AAPL --query "..." --force-refresh
```

## References

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Docling XBRL conversion](https://docling-project.github.io/docling/examples/xbrl_conversion/)
