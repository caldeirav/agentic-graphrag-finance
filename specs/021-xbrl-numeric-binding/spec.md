# Feature Specification: FY Binding, Concept-Aware XBRL, and Numeric Computation

**Feature Branch**: `019-agent-failure-investigation` (spec `021-xbrl-numeric-binding`)

**Created**: 2026-06-23

**Status**: Draft

**Depends on**: `020-agent-capability-first` (structured synthesis, cohort fixture, Principle VII)

**Input**: Move value_alignment on the 26-item XBRL numeric cohort by fixing upstream binding and extraction—not answer formatting. Cohort re-run after 020: template dumps ~18→2, but outcome_score remains 0/26 because abstentions and wrong period/concept numerics dominate; weakest judge criterion is `routing_decisions` (18/26).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - FY Filing Binding (Priority: P1)

When a financebench question asks for **fiscal year 2025** (no quarter language), the agent binds the **10-K** whose fiscal period ends in FY2025—not the latest 10-Q (e.g. 2026 Q1).

**Why this priority**: Most abstentions cite “only 2026 Q1 data available” despite FY2025 10-K in corpus; MRR≥0.5 on 25/26.

**Independent Test**: Cohort-debug re-run; for items with `FY2025` in question or `fiscal_period_labels`, `filing_set` contains a 10-K with period_end in FY2025.

**Acceptance Scenarios**:

1. **Given** “What was revenue for fiscal year 2025?” and corpus has FY2025 10-K + newer 10-Q, **When** macro routing runs, **Then** `filing_set` is the FY2025 10-K only (or YoY pair if comparison).
2. **Given** benchmark metadata `fiscal_period_labels: ["FY2025"]`, **When** binding materializes, **Then** validator does not approve latest 10-Q when quarterly_metric_cue would otherwise fire.
3. **Given** explicit “Q1 2025” language, **When** binding runs, **Then** a matching 10-Q is selected—not forced 10-K.

---

### User Story 2 - Concept-Aware XBRL Fact Selection (Priority: P1)

The agent selects XBRL facts whose **concept and period** match the question metric—not unrelated line items (e.g. `OtherAssetsFairValueDisclosure` for asset *change*).

**Why this priority**: 6/26 re-run answers state wrong `$… billion` values; retrieval already ranks correct chunks.

**Independent Test**: Unit tests on fact catalog + resolution with mocked LLM; cohort items 0436, 0495, 0536 show correct concept family in structured answer metadata.

**Acceptance Scenarios**:

1. **Given** multiple XBRL chunks in evidence, **When** resolution runs, **Then** catalog includes parsed concept, period_start/end, is_annual, concept_family.
2. **Given** “total shareholder equity FY2025”, **When** resolution runs, **Then** selected fact is annual `StockholdersEquity*` for FY2025—not Q1 interim.
3. **Given** segment revenue question, **When** resolution runs, **Then** segment-dimension facts are preferred over consolidated revenue when present in evidence.

---

### User Story 3 - Computed Metrics (Priority: P2)

Questions requiring **delta, ratio, or percent change** are answered with Python-computed values from two or more matched XBRL facts—not a single unrelated level fact or abstention.

**Why this priority**: Cohort includes YoY %, margin, and change-in-assets items with numeric GT requiring arithmetic.

**Independent Test**: Fixture tests for delta, ratio, percent_change; cohort items 0536, 0600, 0667 show non-abstaining answers with stated formula.

**Acceptance Scenarios**:

1. **Given** “change in total assets from FY2024 to FY2025”, **When** synthesis runs, **Then** answer includes delta computed from two annual `Assets` facts (or abstains if second fact missing).
2. **Given** “net profit margin FY2025”, **When** synthesis runs, **Then** answer = earnings ÷ revenue × 100 with both concepts cited.
3. **Given** incomplete fact pair, **When** computation skill runs, **Then** structured payload sets `abstain=true` with reason—not a wrong single fact.

---

### User Story 4 - Remove Live Deterministic Numeric Overrides (Priority: P2)

Live synthesis must not inject answers via `_correct_numeric_from_xbrl` or similar keyword handlers.

**Acceptance Scenarios**:

1. **Given** live path (`USE_MOCK_LLM` unset), **When** LLM returns refusal text, **Then** no substitution from `_try_synthesize_numeric_xbrl`.
2. **Given** USE_MOCK_LLM=1, **When** CI runs, **Then** existing deterministic fixtures still pass.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST infer `TemporalScopeIntent` (anchor, target_fiscal_year, form_preference, comparison_mode) from query + benchmark metadata before finalizing `filing_set`.
- **FR-002**: Macro validator MUST reject or narrow bindings when bound period label mismatches target fiscal year from intent (unless quarter explicitly requested).
- **FR-003**: `detect_quarterly_metric_cue` MUST NOT force 10-Q binding when query specifies annual fiscal year without quarter language.
- **FR-004**: XBRL fact catalog MUST parse concept, period range, display value, and concept_family from evidence excerpts using shared parsing helpers.
- **FR-005**: Fact resolution MUST pre-filter candidates with `xbrl_concept_matches_query` and period filter before LLM selection.
- **FR-006**: System MUST classify numeric questions into metric types: `point`, `delta`, `ratio`, `percent_change`.
- **FR-007**: Computation MUST execute arithmetic in Python from parsed numeric values; LLM MUST NOT perform final math.
- **FR-008**: Extended structured answer schema MUST include `metric_type`, `inputs`, `formula`, and optional `computed_value`.
- **FR-009**: Live synthesis MUST gate `_correct_numeric_from_xbrl` and related deterministic overrides to `USE_MOCK_LLM=1`.
- **FR-010**: Cohort gate on `xbrl_numeric_cohort.json`: mean `value_alignment` ≥ 0.15 vs 020 baseline (0.0); `binding_miss` flags ≤ 5/26.

### Success Criteria

- **SC-001**: ≥15/26 cohort items with `outcome_score > 0` after re-run + judge (operator-measured).
- **SC-002**: Abstention-like answers ≤ 8/26 (down from ~19).
- **SC-003**: Zero answers matching “Per XBRL … bound fiscal period” deterministic template in live path.
- **SC-004**: For FY2025-labeled items, ≥20/26 bind 10-K period_end in FY2025 (trace or cohort_debug `filing_set`).

### Out of Scope

- Publishing v2.0.1 bundle
- Full 200×5 paper-v1.1 repro
- Graph builder segment dimension ingestion (follow-up if catalog lacks segment metadata)
- Replacing external judge

## Assumptions

- 020 structured synthesis and chunk-dump guard remain in place.
- Cohort fixture: `specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json`.
- Corpus contains FY2025 10-K for Exxon/Caterpillar/Apple items in cohort.
