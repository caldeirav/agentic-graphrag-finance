# Feature Specification: Live Regulatory Disclosure Ingestion & Developer CLI

**Feature Branch**: `002-live-disclosure-cli`

**Created**: 2026-05-18

**Status**: Draft

**Input**: User description: "Add a live regulatory disclosure ingestion module and a developer-facing command-line interface (CLI) to the system."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dynamic XBRL Fetch & Resolve (Priority: P1)

A developer needs to pull raw XBRL financial disclosure packages for any U.S. public company on demand, using a CIK, stock ticker, or EDGAR accession number. They invoke a programmatic interface that resolves the identifier to the correct filing set, locates XBRL instance and taxonomy files, and returns validated download targets without manual EDGAR navigation.

**Why this priority**: Live fetch and identifier resolution are prerequisites for any non-benchmark workflow; without them the cache and unified CLI cannot operate on arbitrary issuers.

**Independent Test**: Provide a known CIK and accession for a recent 10-K; verify the module returns a complete XBRL file manifest (instance document plus required taxonomy artifacts) with filing metadata. Delivers value as a standalone fetch API even before cache or full CLI exist.

**Acceptance Scenarios**:

1. **Given** a valid CIK and form type (10-K or 10-Q), **When** the developer requests the latest filing, **Then** the system resolves the correct accession number and returns downloadable XBRL package descriptors.
2. **Given** a valid stock ticker, **When** the developer requests filings, **Then** the system resolves ticker → CIK and returns the same manifest as a direct CIK lookup.
3. **Given** a valid accession number, **When** the developer requests XBRL artifacts, **Then** the system returns all instance and supporting taxonomy files required for structural parsing.
4. **Given** an unknown or delisted ticker, **When** lookup is attempted, **Then** the system returns a clear resolution failure without downloading partial or wrong-issuer data.

---

### User Story 2 - Local Disclosures Asset Cache (Priority: P2)

The developer runs an automated download manager that retrieves multi-file XBRL disclosure packages, verifies structural validity before acceptance, and stores them in a versioned local cache that the existing parsing pipeline can consume on subsequent runs without re-fetching unchanged filings.

**Why this priority**: Caching enables fast iteration, offline re-parse, and repeatable agent runs while respecting regulatory source rate limits.

**Independent Test**: Fetch two filings for one issuer; run parse twice on the second run with cache hit; verify second run skips network download and parsing still succeeds. Delivers value as a local data layer independent of the unified CLI.

**Acceptance Scenarios**:

1. **Given** a resolved XBRL manifest, **When** the cache manager downloads files, **Then** all artifacts are stored under a deterministic issuer/filing path with content hashes recorded.
2. **Given** a previously cached filing with unchanged source hash, **When** a re-fetch is requested, **Then** the system serves from cache and does not re-download unless forced refresh.
3. **Given** a downloaded package, **When** structural validation runs, **Then** invalid or incomplete XBRL sets are rejected and flagged without entering the parse pipeline.
4. **Given** a successful cache write, **When** the parsing pipeline is invoked, **Then** it reads from the cache location using the same contracts as manual ingest paths.

---

### User Story 3 - Unified Developer CLI Workflow (Priority: P3)

The developer runs a single terminal command with a ticker (or CIK) and a natural-language financial question. The CLI automatically fetches (or loads from cache) the relevant filing(s), builds the knowledge graph, executes the agentic retrieval route, and prints a grounded answer with citations and trace reference—bridging live data to the existing graph-grounded agent.

**Why this priority**: This is the end-to-end developer experience that connects live ingestion to production retrieval; it depends on P1 and P2 but delivers the stated real-world utility goal.

**Independent Test**: Run one command: `ticker + question` → grounded answer with chunk citations and a trace/run identifier, on a filing not present in benchmark fixtures. Delivers the full live-analysis loop.

**Acceptance Scenarios**:

1. **Given** a ticker and complex query, **When** the developer runs the unified ask command, **Then** the system fetches or caches filings, builds a graph snapshot, runs agentic retrieval, and renders the grounded response in the terminal.
2. **Given** filings already in cache, **When** the same command is re-run, **Then** the system completes faster by using cached artifacts while producing an equivalent graph and answer path.
3. **Given** a query requiring multiple periods, **When** the CLI executes, **Then** the response declares which filings and periods were used and cites evidence chunks.
4. **Given** insufficient evidence in fetched filings, **When** retrieval completes, **Then** the CLI reports fail-closed status without fabricated figures.

---

### Edge Cases

- What happens when SEC EDGAR is unreachable? The system MUST surface a retryable network error and MUST NOT corrupt the cache with partial writes.
- How are amended or superseded filings handled? Cache entries MUST record filing status; default fetch policy prefers the latest non-superseded artifact for a requested period.
- What happens when XBRL taxonomy files are missing from the package? Validation MUST fail closed and exclude the filing from parse until complete.
- How does the system behave under SEC fair-access rate limits? Requests MUST be throttled with configurable delay and a identifiable user-agent string.
- What happens when ticker maps to multiple CIKs (rare edge)? Resolution MUST disambiguate or fail with explicit guidance.
- What happens when the developer passes both ticker and CIK that conflict? The CLI MUST reject the input with a validation error.
- How are concurrent cache updates handled? Writes MUST be atomic per filing (temp dir + rename) to avoid half-written packages.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a programmatic interface to query U.S. regulatory disclosure systems (SEC EDGAR as primary source) for raw XBRL financial data by CIK, stock ticker, or accession number.
- **FR-002**: System MUST resolve stock tickers to CIK using authoritative issuer mapping data with periodic refresh capability.
- **FR-003**: System MUST resolve “latest filing” requests per form type (minimum 10-K and 10-Q) for a given issuer identifier.
- **FR-004**: System MUST extract and return a manifest of XBRL instance documents and required taxonomy/support files for each resolved filing.
- **FR-005**: System MUST authenticate to regulatory APIs only via configuration (no hard-coded secrets); credentials MUST NOT be stored in source control.
- **FR-006**: System MUST implement a local disclosures asset cache with deterministic directory layout keyed by issuer and accession.
- **FR-007**: Cache manager MUST download all manifest files, verify completeness, and record content hashes per artifact.
- **FR-008**: Cache manager MUST skip re-download when source content hash matches a cached entry unless force-refresh is requested.
- **FR-009**: System MUST validate XBRL package structural integrity before marking a cache entry as parse-ready.
- **FR-010**: Cached artifacts MUST feed the existing parsing pipeline without modifying parser semantics (constitution: parsing layer owns parse rules).
- **FR-011**: System MUST expose a unified developer CLI that orchestrates fetch/cache → graph build → agentic query → formatted response.
- **FR-012**: CLI MUST accept issuer identification via `--ticker`, `--cik`, or `--accession` (at least one required) plus a required `--question` (or positional equivalent).
- **FR-013**: CLI MUST support optional flags for form type, filing date range, force cache refresh, and snapshot reuse.
- **FR-014**: CLI output MUST include grounded answer text, evidence citations, filing scope used, and trace/run identifier for audit.
- **FR-015**: CLI MUST integrate with existing agentic retrieval (not a parallel query path) and respect fail-closed grounding rules.
- **FR-016**: System MUST log fetch and cache operations with enough metadata for debugging (issuer, accession, timestamps, cache hit/miss).
- **FR-017**: Live fetch module MUST remain within the parsing/ingest concern boundary; it MUST NOT implement graph building, agent routing, or benchmark evaluation logic.
- **FR-018**: Unified CLI MAY orchestrate across layers but MUST call each layer only through established public contracts.

### Key Entities

- **IssuerIdentifier**: CIK, ticker, or accession supplied by the developer.
- **FilingResolution**: Resolved filing metadata (form type, dates, accession, EDGAR URLs).
- **XBRLArtifactManifest**: List of files to download with roles (instance, taxonomy, label, presentation, etc.).
- **CacheEntry**: Local path, content hashes, validation status, parse-ready flag, cached-at timestamp.
- **FetchJob**: A single fetch attempt with status (pending, complete, failed) and error detail.
- **CLIRequest**: User inputs (identifier, question, options) mapped to pipeline stages.
- **CLIResult**: Answer package, citations, trace handle, timing summary for terminal display.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 10 known large-cap tickers, identifier resolution succeeds in under 5 seconds per issuer in 95% of attempts under normal network conditions.
- **SC-002**: For a valid recent 10-K, XBRL manifest completeness validation passes in 98% of fetches (instance + required taxonomy files present).
- **SC-003**: Cache hit on repeat parse of the same filing reduces end-to-end CLI time by at least 50% versus cold fetch (same machine, same corpus).
- **SC-004**: Developer can complete ticker + question → grounded cited answer on a filing outside benchmark fixtures in one CLI invocation, with success on 90% of trial runs for well-formed large-cap issuers.
- **SC-005**: Zero cache entries marked parse-ready fail structural validation on re-read (no corrupt half-packages in cache).
- **SC-006**: 100% of CLI responses that include numeric claims also include at least one supporting evidence citation, or explicitly report insufficient evidence.
- **SC-007**: Invalid identifier inputs produce actionable error messages (not stack traces) in 100% of negative test cases.

## Assumptions

- Builds on the existing `001-sec-disclosure-rag` implementation (parsing, graph, retrieval, evaluation layers already exist).
- Primary regulatory source is SEC EDGAR (U.S. issuers); other jurisdictions are out of scope for v1.
- Ticker resolution uses SEC-published company ticker mappings refreshed on a configurable schedule (default: daily).
- Developer CLI targets engineers and researchers, not retail end users; no interactive UI beyond terminal output.
- Rate limiting defaults align with SEC EDGAR fair access guidance (configurable requests-per-second and user-agent).
- v1 unified CLI orchestrates ingest + graph + query; benchmark suite execution remains a separate command.
- Authentication to EDGAR is public-read for standard filings; no premium data vendor integration in v1.
