# Feature Specification: Multi-Filing Issuer Corpus & Temporal Snapshots

**Feature Branch**: `003-multi-filing-corpus`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Add multi-filing corpus management for a single U.S. public issuer: ability to fetch, cache, and materialize a versioned graph snapshot that includes multiple 10-K and / or 10-Q filings. System interaction (CLI and benchmarks) leverage temporal scope in the request (e.g., latest annual or prior quarter) to retrieve and bind necessary documents to fulfill the request. Success: an analyst can ask multiple-period queries or period-comparison questions and see which documents, periods and accessions were included in the snapshot."

## Clarifications

### Session 2026-05-20

- Q: When corpus materialization would exceed the configured maximum (default 12 filings), what should the system do? → A: Require explicit narrowing — reject until the user supplies a narrower corpus definition (date range, count, or explicit accession list).
- Q: For the default analyst/CLI workflow, when should multi-filing corpus materialization run relative to a question? → A: Default corpus + query binding — materialize a default issuer snapshot up front; per question bind only needed periods (fetch and extend if outside snapshot).
- Q: How should the system interpret period labels such as “Q3” or “prior quarter” when resolving temporal scope? → A: Issuer fiscal periods only — “Q3” and “prior quarter” always map to fiscal year-quarter labels from filing metadata.
- Q: When a newer SEC filing exists for the issuer but the analyst reuses an existing snapshot version, what should happen? → A: Warn and proceed — allow the query but flag stale snapshot status and list newer available filings/periods not in the snapshot.
- Q: How should benchmarks supply temporal scope compared to the CLI? → A: Split by entry point — benchmarks MUST use structured temporal-scope fields; CLI MAY use NL in the question and/or optional explicit scope flags.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Filing Corpus Snapshot for One Issuer (Priority: P1)

A financial analyst (or developer acting on their behalf) needs a durable, versioned knowledge snapshot for a single U.S. public company that combines multiple annual (10-K) and/or quarterly (10-Q) filings—not just the latest single filing. They request corpus materialization for an issuer; the system fetches or reuses cached disclosure packages, validates them, and produces one issuer-level snapshot that embeds all included filings with identifiable periods and accession references.

**Why this priority**: Multi-period reasoning and comparisons are impossible without a managed corpus and unified snapshot; this is the data foundation for temporal queries.

**Independent Test**: Materialize a snapshot for a large-cap issuer including the latest 10-K and the two most recent 10-Q filings; verify the snapshot version identifier, filing count, and per-filing period/accession manifest without running a full Q&A session.

**Acceptance Scenarios**:

1. **Given** a valid issuer identifier and a corpus definition listing at least two filings (e.g., latest 10-K plus latest 10-Q), **When** corpus materialization runs, **Then** the system produces a versioned snapshot that references every requested filing and marks each as included or failed with reason.
2. **Given** some filings already in local cache, **When** corpus materialization runs, **Then** cached artifacts are reused for unchanged filings and only missing or stale filings are fetched from the regulatory source.
3. **Given** a successful materialization, **When** the analyst inspects snapshot metadata, **Then** they see issuer identity, snapshot version, creation time, and a list of included filings with form type, fiscal/report period, filing date, and accession identifier.
4. **Given** a filing package that fails structural validation, **When** materialization completes, **Then** that filing is excluded from the snapshot, the failure is recorded, and the snapshot version reflects partial corpus status without silent omission.

---

### User Story 2 - Temporal Scope in Queries and Benchmarks (Priority: P2)

An analyst asks questions that imply time—such as “latest annual report,” “prior quarter,” “compare Q3 to Q2,” or “year-over-year revenue trend over the last four quarters.” The default workflow pre-materializes a standard issuer snapshot (latest 10-K plus trailing quarterly reports); each question then resolves temporal intent, binds only the filings needed for that question from the snapshot, and fetches plus publishes a new snapshot version only when a required period is outside the current snapshot.

**Why this priority**: Temporal scope is how users select which slice of the multi-filing corpus to use; without resolution, multi-filing storage delivers no query-time value.

**Independent Test**: Run a benchmark case with structured “prior quarter” scope and a CLI question with the same intent in natural language for a known issuer; verify equivalent accession bindings and matching manifest fields (benchmark via structured scope, CLI via NL resolution).

**Acceptance Scenarios**:

1. **Given** a default issuer snapshot is already materialized, **When** the user asks a question scoped to “latest annual,” **Then** the system binds only the most recent 10-K from that snapshot and records that binding before retrieval proceeds.
2. **Given** a question requires a period not present in the current snapshot, **When** temporal resolution runs, **Then** the system fetches the missing filing, publishes a new snapshot version including it, and records the binding against that new version.
3. **Given** a comparison-style question (e.g., two named quarters or “current vs prior quarter”), **When** the request is processed, **Then** the system binds at least two distinct periods’ filings and refuses to answer comparatively if a required period cannot be resolved.
4. **Given** ambiguous temporal language with a unique sensible default for the issuer (e.g., only one recent 10-Q), **When** resolution runs, **Then** the system applies the default, documents the assumption in the binding manifest, and proceeds.
5. **Given** temporal language that cannot be mapped to any filing in scope (e.g., “Q1 2010” when corpus only covers trailing eight quarters), **When** resolution runs, **Then** the system reports an out-of-scope period error with guidance on available periods—without fabricating data.

---

### User Story 3 - Analyst-Visible Snapshot Transparency (Priority: P3)

After any multi-period or comparison query—or after corpus materialization—the analyst reviews which disclosures actually powered the result. The system surfaces a human-readable binding manifest: documents included, reporting periods, form types, filing dates, and accession identifiers, aligned with the snapshot version used.

**Why this priority**: Trust and auditability for financial analysis require explicit provenance; this is the stated success condition for the feature.

**Independent Test**: Execute a period-comparison question; confirm terminal or benchmark output includes a “snapshot scope” section listing every bound accession and period, matching the persisted snapshot manifest for that run.

**Acceptance Scenarios**:

1. **Given** a completed query against a multi-filing snapshot, **When** results are presented, **Then** output includes a snapshot scope summary listing every bound document with period label, form type, and accession identifier.
2. **Given** a comparison query where only one of two periods was available, **When** results are presented, **Then** output states which period was missing and does not present a comparative conclusion as grounded fact.
3. **Given** a benchmark run with expected temporal bindings, **When** the run finishes, **Then** evaluation artifacts record the same binding manifest fields so automated checks can verify correct document selection.
4. **Given** snapshot version N was used, **When** the analyst reviews trace or run metadata, **Then** they can correlate the answer to snapshot version N and its immutable filing list without re-deriving bindings from memory.
5. **Given** a newer filing exists on the regulatory source than is included in snapshot version N, **When** a query runs without forced refresh, **Then** results proceed but the snapshot scope summary flags stale status and lists newer available periods/accessions not in version N.

---

### Edge Cases

- What happens when the issuer has no 10-Q history (e.g., newly public)? Temporal resolution MUST surface available form types and fail clearly for quarter-scoped requests that cannot be satisfied.
- How are amended or superseded filings handled? Corpus entries MUST prefer the latest non-superseded filing for a given period; superseded accessions MUST remain visible in history but MUST NOT be default-bound for “latest” scopes.
- What happens when two filings claim the same fiscal period? The system MUST detect duplicates, apply a documented precedence rule (latest filing date wins unless user specifies accession), and record the decision in the binding manifest.
- How does the system behave when corpus size exceeds configured limits? Materialization MUST fail closed and require the user to narrow scope (date range, filing count, or explicit accession list); the system MUST NOT truncate, silently drop filings, or publish a partial snapshot without an explicit narrowed definition.
- What happens when network or regulatory source is unavailable for one filing in a multi-filing job? Partial materialization MUST complete for valid filings, mark failures per filing, and block queries that depend on missing filings.
- How are concurrent materializations for the same issuer handled? Only one write MUST succeed per snapshot version increment; concurrent attempts MUST not corrupt shared cache directories.
- What happens when temporal scope in a query conflicts with an explicitly supplied accession list? The system MUST reject the request with a validation error explaining the conflict.
- What happens when a benchmark case omits structured temporal-scope fields? The benchmark runner MUST fail the case at setup with a validation error (not at retrieval time).
- What happens when the CLI supplies both explicit temporal-scope flags and conflicting NL in the question? Explicit flags override when reconcilable; irreconcilable conflict MUST yield a validation error per FR-009c.
- What happens when a user says “calendar Q3” for a non-December fiscal-year issuer? The system MUST treat unqualified quarter labels as fiscal-only; explicit calendar date ranges may select filings by filing date, with the binding manifest stating the date-range basis.
- What happens when the analyst reuses an older snapshot but EDGAR has newer filings? Queries MUST proceed (unless the user forces refresh) with stale snapshot status and a list of newer available filings/periods in the snapshot scope summary; “latest” temporal scopes MUST NOT silently bind to older filings without the stale warning.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST manage an issuer-level disclosure corpus scoped to exactly one U.S. public company per corpus instance, keyed by authoritative issuer identity (e.g., CIK or resolved ticker).
- **FR-002**: System MUST support inclusion of multiple regulatory filings per corpus, with at minimum annual reports (10-K) and quarterly reports (10-Q) as distinct includable members.
- **FR-003**: System MUST fetch missing disclosure packages from authoritative regulatory sources, reuse validated local cache when content is unchanged, and record per-filing cache hit or miss status.
- **FR-004**: System MUST validate each disclosure package for structural completeness before marking it eligible for snapshot inclusion.
- **FR-005**: System MUST materialize a versioned graph snapshot that aggregates all eligible filings in the corpus definition into one issuer-level artifact with a monotonically identifiable version identifier.
- **FR-006**: Each snapshot version MUST be immutable once published; changes to corpus membership MUST create a new snapshot version rather than altering a prior version in place.
- **FR-007**: System MUST persist snapshot metadata including issuer identity, version, creation timestamp, corpus definition inputs, and per-filing inclusion status (included, excluded, failed).
- **FR-007a**: When a corpus definition exceeds the configured filing maximum, materialization MUST reject the request with an actionable error (requested vs allowed counts) and MUST NOT publish a snapshot until the user supplies a narrower corpus definition.
- **FR-008**: System MUST expose temporal scope resolution that maps user or benchmark-supplied time expressions (e.g., latest annual, prior quarter, named fiscal period, comparison pairs) to concrete filings within the active snapshot, fetching and publishing a new snapshot version when a required period is absent.
- **FR-008b**: Temporal scope resolution MUST interpret period labels (e.g., “Q3,” “prior quarter,” “latest quarter”) using the issuer’s fiscal year-quarter labels from filing metadata only; calendar-quarter mapping is out of scope unless the user supplies an explicit calendar date range that unambiguously selects filings.
- **FR-008a**: Default analyst/CLI workflow MUST pre-materialize the standard default issuer snapshot (latest 10-K plus four trailing 10-Qs unless narrowed) before or as part of the first question for that issuer, then bind only the subset of filings required per question without re-materializing the full default corpus on every query.
- **FR-009**: Command-line and benchmark entry points MUST produce equivalent binding manifests for equivalent temporal intent, issuer, and corpus state.
- **FR-009a**: Benchmark cases MUST supply temporal scope via structured, machine-readable fields (fiscal periods, comparison sets, and/or explicit accessions); benchmarks MUST NOT rely on natural-language temporal parsing alone.
- **FR-009b**: CLI MUST support temporal resolution from natural language in the question and MAY accept optional explicit temporal-scope flags; when explicit CLI flags are supplied, they override NL-derived scope for binding.
- **FR-009c**: When CLI explicit scope flags and NL-derived scope irreconcilably conflict, the system MUST reject the request with a validation error.
- **FR-010**: Before retrieval or answering, the system MUST bind the resolved set of filings for the request and MUST NOT use filings outside that binding for grounded outputs.
- **FR-011**: System MUST support multi-period analytical questions and period-comparison questions that require two or more distinct reporting periods, failing closed when any required period cannot be bound.
- **FR-012**: Every analytical response and benchmark outcome that uses the corpus MUST include a snapshot scope summary listing bound documents with reporting period, form type, filing date, and accession identifier.
- **FR-012a**: When the active snapshot version is older than filings available on the regulatory source for the issuer, the snapshot scope summary MUST include a stale-snapshot indicator and enumerate newer available periods/accessions not included in the active version (queries MUST NOT be blocked solely for staleness).
- **FR-013**: System MUST correlate each analytical run with the snapshot version and binding manifest used, retained in durable trajectory records suitable for audit and benchmark replay.
- **FR-014**: System MUST enforce fail-closed grounding: numeric or comparative claims MUST cite evidence from bound filings or explicitly state insufficient evidence.
- **FR-015**: System MUST respect regulatory fair-access constraints (throttling, identifiable client identity) when fetching multiple filings in one corpus job.
- **FR-016**: Corpus management MUST remain separable from retrieval orchestration: building and versioning snapshots MUST be invocable without executing a user question; retrieval MUST consume published snapshot contracts only.
- **FR-017**: Benchmark suites applicable to multi-period selection MUST be able to assert expected bindings (periods and accessions) against actual bindings recorded for each run.

### Key Entities

- **IssuerCorpus**: The managed set of disclosure packages and metadata for one U.S. public issuer; defines membership rules (which filings to include) and cache state.
- **CorpusMember**: A single filing within the corpus—form type, fiscal/report period, filing date, accession identifier, validation status, cache location reference.
- **CorpusMaterializationJob**: A run that fetches, validates, and assembles members into a new snapshot version; tracks per-member success and failure.
- **GraphSnapshotVersion**: An immutable issuer-level knowledge snapshot aggregating one or more corpus members, with version id and structural graph identity for downstream retrieval.
- **TemporalScope**: Parsed time intent from user or benchmark input (e.g., latest annual, prior quarter, explicit fiscal year-quarter, comparison set), always resolved to issuer fiscal period labels from filing metadata.
- **FilingBinding**: The resolved subset of corpus members active for a specific query or benchmark case, with resolution rationale and defaults applied.
- **SnapshotScopeManifest**: Human- and machine-readable record of snapshot version, bound filings, periods, accessions, stale-snapshot status (if applicable), newer-available filing hints, and any exclusions or failures material to the run.
- **BindingManifestRecord**: Persisted trajectory artifact linking a query or benchmark run to its SnapshotScopeManifest and snapshot version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 10 large-cap issuers, an analyst can materialize a corpus of at least three filings (one 10-K and two 10-Q) in under 10 minutes on a typical broadband connection when starting from cold cache, with 90% success rate excluding regulatory outages.
- **SC-002**: Repeat materialization of an unchanged corpus completes at least 50% faster than cold fetch by reusing cache for all unchanged members in 95% of trials.
- **SC-003**: For a standardized set of 20 temporal-scope benchmark prompts across five issuers, correct filing binding (matching expert-labeled accessions) is achieved in at least 85% of runs.
- **SC-004**: 100% of successful multi-period or comparison query outputs include a snapshot scope summary with at least one accession per bound period; zero successful runs omit provenance fields.
- **SC-005**: When a required period for a comparison query is unavailable, 100% of runs report missing-period status and produce zero unqualified comparative numeric claims in output.
- **SC-006**: Analysts reviewing run metadata can identify snapshot version and full binding list without re-running materialization in 100% of audited sample runs.
- **SC-007**: Invalid or structurally incomplete filing packages are excluded from snapshots with documented failure reasons in 100% of negative validation test cases—no silent inclusion.

## Assumptions

- Target issuers are U.S. public companies with filings available through SEC EDGAR; foreign-only issuers are out of scope for this feature.
- Supported form types for v1 corpus membership are 10-K and 10-Q only; other forms (8-K, proxy) may be added in a later feature.
- Default corpus depth when the user does not specify otherwise is the latest annual report plus the four most recent quarterly reports (trailing five filings), subject to a configurable maximum (default cap: 12 filings per issuer snapshot) to bound storage and build time.
- Default analyst/CLI workflow pre-materializes that standard snapshot once per issuer session (or reuses the latest published version if still current), then binds a per-question subset; missing periods trigger fetch and a new snapshot version rather than full lazy per-question materialization.
- Temporal expressions in natural language are resolved against issuer fiscal year-quarter labels and filing dates embedded in filing metadata; unqualified quarter references (e.g., “Q3,” “prior quarter”) never use calendar-quarter mapping.
- A single issuer-level snapshot merges multiple filings into one navigable knowledge structure with explicit per-filing boundaries and temporal linkage (e.g., sequential quarter relationships), rather than maintaining disconnected single-filing snapshots without cross-filing context.
- Existing single-filing fetch and cache capabilities from prior features are reused; this feature extends orchestration, versioning, binding, and transparency—not raw download mechanics.
- Analyst-facing transparency is delivered through CLI output fields and benchmark/run artifacts; a separate graphical UI is out of scope.
- Evaluation and trajectory retention follow project constitution requirements: bindings and snapshot versions are persisted for audit and automated benchmark verification.
- Benchmark temporal scope is always structured for reproducibility; CLI temporal scope may be natural-language, explicit flags, or both (explicit flags override NL when both are present).
