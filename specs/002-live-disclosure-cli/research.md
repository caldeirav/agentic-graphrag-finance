# Research: Live Disclosure Ingestion & Developer CLI

**Date**: 2026-05-18 | **Plan**: [plan.md](./plan.md)

## R1: sec-api vs Native EDGAR Scraping

**Decision**: Use official **`sec-api`** Python package (`uv add sec-api`) with `SEC_API_KEY` from environment.

**Rationale**: User mandate; sec-api provides filing query, CIK mapping, and download APIs with documented rate limits—reduces breakage vs HTML scraping. Aligns with spec FR-005 (secrets in env only).

**Alternatives considered**:
- Extend existing `parsing/edgar_fetch.py` (httpx only) — rejected for XBRL artifact discovery complexity
- Direct EDGAR index.json parsing — rejected; maintenance burden and fair-access compliance

**Implementation notes**:
```python
from sec_api import QueryApi, RenderApi, XbrlApi  # subset per need
# Initialize with os.environ["SEC_API_KEY"]
```

## R2: Storage Path Convention

**Decision**: `data/raw/sec_downloads/{ticker}/{accession_number}/` as canonical live pool.

**Rationale**: User-specified layout; ticker-first aids CLI UX; accession disambiguates amended filings.

**Migration**: Keep `data/raw/edgar/{cik}/` for backward compatibility; `parsing` accepts either via `CacheEntry.local_path`.

## R3: Ingestion Package Boundary

**Decision**: New top-level `src/ingestion/` (not nested under `parsing/`).

**Rationale**: Constitution separation—fetch/cache/validate vs Docling parse. Spec FR-017 allows ingest concern; dedicated package clarifies imports for contract tests.

**Public API**: `fetch_filing()`, `resolve_identifier()`, `get_cache_entry()`.

## R4: CLI Framework & Entry Point

**Decision**: **Typer** (add `uv add typer` if not present) in `src/cli/main.py`; script name **`agent-query`**.

**Rationale**: Subcommands `ask` and `test` map cleanly; `uv run agent-query` matches user requirement.

**Alternatives considered**:
- Extend scattered `sec-*` scripts — rejected; unified orchestration needs single entry
- Click only — Typer preferred for typed options and help generation

## R5: Orchestration Sequence

**Decision**: `cli/pipeline.py` implements explicit staged pipeline with timing logs:

```text
resolve_id → fetch (1A) → parse (1B) → graph build → QueryService.answer → format stdout
```

**Rationale**: Matches user Phase 5 sequence; each stage calls existing services.

**MLflow**: Parent run `agent-query-{ticker}` with nested query run from `QueryService`.

## R6: Test / Evaluation Mode

**Decision**: `agent-query test` runs:
1. Fetch latest 10-K for ticker (or use `--accession`)
2. Build graph
3. Assert minimum node counts (document, section, chunk_table) and manifest hash stability

Optional `--registry specs/001-.../contracts/` thresholds file.

**Rationale**: Supports CI without full benchmark suite; complements `evaluation.cli benchmark`.

## R7: SEC_API_KEY Guardrails

**Decision**: `ingestion/settings.py` with `require_sec_api_key()` called at:
- `sec_client` module init (lazy)
- CLI `ask` / `test` command entry

CI sets `SEC_API_KEY=test-mock` or mocks HTTP.

**Rationale**: Fail fast with actionable message; never read key from source code.

## R8: Rate Limiting & Errors

**Decision**: Configurable `SEC_API_REQUESTS_PER_SECOND` in `.env` (default 2); exponential backoff on 429/5xx.

**Rationale**: sec-api.io account limits; spec edge case for unreachable API.

## Resolved Clarifications

All technical context items resolved for Phase 1 design.
