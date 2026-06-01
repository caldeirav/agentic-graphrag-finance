# Feature Specification: Benchmark Evaluation Acceleration

**Feature Branch**: `013-benchmark-eval-acceleration`

**Created**: 2026-06-01

**Status**: Draft

**Input**: Feature 013: Benchmark evaluation acceleration — deferred judging, per-item subgraphs, and resumable full repro. Depends on research reproduction kit (012, merged), trajectory judge evaluation (010), and custom-judge dataset (011).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deferred and Batched Judging (Priority: P1)

An evaluation engineer running full paper reproduction wants agent variants to produce answers and retrieval trajectories first, then score them in a separate batched judging phase, so that long runs are not blocked by per-question external judge latency and judging can be restarted independently.

**Why this priority**: Judging coupled to every agent answer is a major contributor to multi-day reproduction wall-clock; decoupling unlocks faster generation phases and parallel judge throughput.

**Independent Test**: Run a 20-item smoke reproduction with deferred judging enabled; verify the generation phase completes with no external judge calls per item, then a judge-batch phase scores all items and headline tables include only fully judged items.

**Acceptance Scenarios**:

1. **Given** deferred judging is enabled for reproduction, **When** a graph-grounded variant scores an item, **Then** the system records answers and trajectories without invoking external judge scoring during answer generation, and item results show judge status as pending until batch judging completes.
2. **Given** all items for a variant have answers stored, **When** the judge batch phase runs, **Then** exactly one external judge evaluation per item is performed using the same criteria as production trajectory judging, results are merged into per-variant outputs, and judge status becomes completed or degraded.
3. **Given** judge batch fails after processing half the items, **When** the operator re-runs judge batch only, **Then** only items without final judge scores are evaluated; already-judged items are not re-scored.
4. **Given** deferred judging is enabled, **When** the flat-chunk baseline runs, **Then** judging is also deferred during chunk retrieval and answer generation (no duplicate judge during generation).
5. **Given** deferred judging is disabled (default for interactive single-question use), **When** an operator asks a question through the standard query interface, **Then** post-query judge audit behavior is unchanged from current production.

---

### User Story 2 - Per-Item Graph Scope (Priority: P1)

An evaluation engineer wants each benchmark item to load only the disclosure graph data for issuers referenced in that item's expected filings, so navigation and planning run on smaller graphs and reproduction is faster without weakening offline corpus guarantees.

**Why this priority**: Loading the full multi-issuer corpus for every item wastes memory and traversal time when most items target one or two issuers.

**Independent Test**: Run reproduction on a mix of single-issuer and two-issuer items; verify logged graph scope matches expected filings only, single-issuer items use materially smaller graphs than full-corpus merge, and cross-issuer items still retrieve evidence when sections exist in both issuer graphs.

**Acceptance Scenarios**:

1. **Given** a benchmark item referencing a single issuer's filings, **When** a graph-grounded variant runs, **Then** only that issuer's bundled graph snapshots are loaded and merged for that item—not the entire issuer universe in the corpus bundle.
2. **Given** a multi-filing item referencing two issuers, **When** reproduction runs, **Then** exactly those two issuer snapshots are merged into the working graph for that item.
3. **Given** an item references accessions not present in any bundled snapshot, **When** reproduction runs, **Then** the workflow fails fast with the item identifier and missing accession list—no silent fallback to an arbitrary default issuer graph.
4. **Given** bundle-level relevance label materialization, **When** it runs, **Then** it may still use the full composite corpus (unchanged); only per-item agent evaluation uses the reduced graph slice.
5. **Given** consecutive items share the same issuer set, **When** reproduction processes them in sequence, **Then** graph data for that issuer set is reused from an in-memory cache without reloading from disk for each item.

---

### User Story 3 - Resumable Full Reproduction (Priority: P1)

An operator running overnight paper reproduction wants to resume after interruption (crash, manual stop, or machine sleep) without re-running completed variants or items, so long batches are recoverable and partial progress is visible on disk.

**Why this priority**: Full reproduction spans hours or days; without first-class resume, a single failure near the end forces expensive rework.

**Independent Test**: Start a multi-variant run, interrupt after partial variant completion, restart with resume enabled; verify completed items and variants are skipped, remaining work continues, and final table export reflects all variants when complete.

**Acceptance Scenarios**:

1. **Given** a reproduction run with partial per-variant results (e.g., 150 of 200 items scored for graph-full), **When** the operator restarts with resume enabled, **Then** graph-full continues from item 151 through 200 and proceeds to subsequent variants without re-scoring the first 150 items.
2. **Given** a variant is fully complete (all planned items scored and judge complete when deferred mode is used), **When** reproduction restarts, **Then** that variant is skipped entirely and the next incomplete variant begins (or resumes its own checkpoint).
3. **Given** resume is disabled via explicit fresh-start flag, **When** reproduction runs, **Then** existing partial results are ignored or cleared per documented policy and all items are scored from scratch.
4. **Given** relevance labels already exist with coverage at or above the publish gate, **When** reproduction restarts, **Then** relevance materialization is skipped (formalized from 012 behavior with tests).
5. **Given** all variants finished but table export did not run, **When** the operator runs export-only recovery, **Then** paper tables are produced from existing per-variant results without re-running agents.
6. **Given** a long reproduction run, **When** each item completes, **Then** a run-state record at the output root is updated with completed variants, per-variant item counts, and last error if any—supporting operator visibility and recovery.

---

### Edge Cases

- **Empty expected filings on an item**: Fail fast with a clear error (paper-v1.0 items are expected to always declare bindings); do not silently use full corpus.
- **Deferred judging with incomplete trajectory**: Batch judge marks item as not evaluable; item is excluded from headline aggregates per existing trajectory completeness rules (010).
- **Concurrent judge batch updates**: Per-variant result files are updated atomically (write-temp-then-rename) to avoid corruption.
- **Partial LFS corpus**: Unchanged from 012—verify-corpus fails fast with missing artifact list.
- **Export with pending judge items**: Headline aggregates exclude pending items; audit table lists them explicitly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Reproduction MUST support an explicit deferred-judging mode (environment flag and CLI flag) on run, run-all, and variant run commands.
- **FR-002**: When deferred judging is active, answer generation for reproduction MUST NOT invoke external trajectory judging during per-item agent execution.
- **FR-003**: Reproduction MUST provide a judge-batch phase that scores pending items with one external judge evaluation per item, equivalent to production trajectory judge criteria.
- **FR-004**: Judge-batch MUST support configurable concurrency (default suitable for single API key rate limits) with safe retry on transient failures.
- **FR-005**: Reproduction MUST persist sufficient trajectory and answer payload in per-item results to enable deferred judging without re-running agents.
- **FR-006**: Table export MUST either wait until judge phase is complete for included items, OR exclude pending items from headline aggregates and list them in an audit table.
- **FR-007**: At reproduction start, the system MUST build an index mapping filing accessions to bundled issuer graph snapshots from the dataset manifest and sampling manifest.
- **FR-008**: For each benchmark item, graph-grounded variants MUST load and merge only issuer snapshots required by that item's expected filing bindings.
- **FR-009**: When an item references accessions not found in the bundle index, reproduction MUST fail with item id and missing accessions—no default-issuer fallback.
- **FR-010**: Flat-chunk baseline evaluation MUST use the same per-item graph scope policy as graph variants unless documented otherwise in operator guide (default: per-item slice for consistency).
- **FR-011**: Reproduction MUST log per item: variant, item id, progress fraction, issuers loaded, and approximate graph size (node or filing count).
- **FR-012**: Reproduction run-all MUST default to resume mode; a fresh-start flag MUST be available to ignore or reset prior partial outputs per documented policy.
- **FR-013**: Variant-level resume MUST skip variants where all planned items are scored and judge is complete (when deferred mode applies).
- **FR-014**: Item-level resume MUST skip items already present in per-variant result checkpoints without duplicate item ids.
- **FR-015**: Reproduction MUST maintain an atomic run-state file at the output directory root updated after each item (and on variant boundaries).
- **FR-016**: Reproduction MUST provide export-only and judge-batch recovery commands for operator recovery without re-running agents.
- **FR-017**: Operator documentation MUST describe recovery: interrupt handling, verifying partial results, restart commands, and resetting a single variant by removing its output directory.

### Key Entities

- **Reproduction run state**: Output-root record of started time, release tag, completed variants, current variant, per-variant item counts, judge phase status, last error.
- **Per-variant results**: Ordered collection of per-item scores, answers, trajectories, judge status, and metrics—checkpointed incrementally.
- **Item graph scope**: The set of issuer snapshots and filings loaded for one benchmark item derived from expected bindings.
- **Judge batch job**: A recoverable phase that transitions items from pending to scored judge status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 20-item reproduction smoke with deferred judging, the generation phase completes with zero external judge API calls during the per-item loop (verifiable via run logs or tracing).
- **SC-002**: Judge-batch restart after simulated mid-run failure processes only remaining items; no duplicate judge scores for already-completed items.
- **SC-003**: On a 10-item smoke, median per-item time for graph-grounded variants improves by at least 25% with per-item graph scope versus full multi-issuer corpus load (same model pins, documented measurement procedure).
- **SC-004**: Cross-issuer multi-filing smoke items produce non-empty retrieved evidence when expected sections exist in both issuer graphs.
- **SC-005**: Interrupting reproduction after 5 items and resuming completes the remaining items without duplicate item ids in per-variant results.
- **SC-006**: Interrupting between variants and resuming does not re-run a fully completed variant.
- **SC-007**: Export-only recovery produces headline and profile tables from existing partial variant results with an audit listing missing variants or pending judge items.

## Assumptions

- Paper-v1.0 reproduction continues to use live agent and live external judge when mock flags are off; deferred judging changes timing, not judge criteria.
- Custom-judge v1.0+ bundle layout remains `corpus/graphs/{issuer}/{snapshot}` with manifest-listed issuer snapshots.
- Reference machine has a single local agent model endpoint; judge-batch concurrency default is modest (e.g., 2) for external API rate limits only.
- Item-level checkpointing from 012 remains the base; this feature extends variant-level and judge-phase resume.
- Benchmark-fast macro/section skip (option A) is out of scope for this feature and may be a follow-on.

## Dependencies

- Feature 012 research reproduction kit (merged): `agent-query repro`, release manifests, composite relevance materialization.
- Feature 010 trajectory judge evaluation: completeness rules and judge criteria.
- Feature 011 custom-judge dataset: `expected_bindings`, `expected_section_paths`, published bundles.

## Out of Scope

- Changing interactive `ask` behavior when deferred judging is not enabled.
- Parallel local agent workers or cloud LLM scale-out (separate feature).
- Benchmark-fast mode that skips macro discovery or jumps directly to known sections (option A).
