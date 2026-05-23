# Feature Specification: Autonomous Macro Routing for Filing & Temporal Scope

**Feature Branch**: `008-autonomous-macro-routing`

**Created**: 2026-05-23

**Status**: Draft

**Input**: Enhance macro-routing so an autonomous agent selects the correct filing set and temporal scope before section navigation: map natural-language references (annual report, latest quarter, previous quarter, year-over-year) to concrete form types and reporting periods; filter the active filing set to only those accessions; detect fiscal-period misalignment across selected filings and fail closed or narrow scope with an explicit message. Every query must record the selected filings, comparison mode, and rationale in the durable trajectory. Success: on a labeled FinAgentBench-style subset, at least 80% of items require multi-filing selection and the agent picks the same filing set as the benchmark rubric in at least 70% of cases.

## Clarifications

### Session 2026-05-23

- Q: When fiscal periods misalign and both fail-closed and narrow-scope are possible, which is the default? → A: Fail closed by default; narrow scope only when a single valid anchor remains and comparison intent is dropped or downgraded with explicit trajectory documentation.
- Q: What is the default year-over-year filing pairing rule for live queries? → A: Quarterly metric → latest 10-Q plus same fiscal-quarter prior-year 10-Q; annual or unspecified YoY → latest two 10-Ks.
- Q: Is macro routing primarily rule-based or LLM-based? → A: LLM proposes the filing set and temporal scope first; a deterministic validator must approve the binding or fail closed before retrieval.
- Q: Where does the labeled evaluation subset for SC-001/SC-002 live? → A: Extend the in-repo FinAgentBench registry (and aligned temporal benchmark cases) with expected_bindings and multi_filing_required flags for a dedicated macro-routing eval slice (≥50 items).
- Q: What is the default quarter-over-quarter (QoQ) filing pairing rule? → A: Latest 10-Q plus immediately prior 10-Q by period end (sequential quarter).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Natural-language period selection (Priority: P1)

An analyst asks a question in plain language (e.g., “What was revenue in the previous quarter?” or “Summarize risk factors in the latest annual report”) without specifying accession numbers or fiscal labels. The system interprets the temporal intent, selects the matching filing(s) from the issuer’s materialized corpus, and proceeds to retrieval only on that narrowed set.

**Why this priority**: Most real queries are phrased in business language; incorrect filing choice invalidates every downstream answer.

**Independent Test**: Run a fixed set of single-filing queries against a corpus with known fiscal metadata; compare selected accessions to expert labels in the benchmark rubric.

**Acceptance Scenarios**:

1. **Given** a materialized multi-filing corpus for an issuer and a query referencing “latest quarter,” **When** the user submits the query without CLI period flags, **Then** the system binds exactly one 10-Q accession whose reporting period matches the latest quarter in the corpus manifest.
2. **Given** a query referencing “annual report” or “10-K,” **When** no explicit accession is provided, **Then** the system binds the latest 10-K accession for that issuer.
3. **Given** a query referencing “previous quarter” or “prior quarter,” **When** the corpus contains at least two quarterly filings, **Then** the system binds the second-most-recent 10-Q by period end, not the latest.

---

### User Story 2 - Multi-filing comparison scope (Priority: P1)

An analyst asks a comparison question (e.g., “How did revenue change year over year?” or “Compare this quarter to the same quarter last year”). The system selects two or more filings with aligned comparison intent, sets an appropriate comparison mode, and restricts evidence retrieval to those accessions.

**Why this priority**: A large share of financial questions require more than one filing; macro routing must support this before meso/micro navigation.

**Independent Test**: On benchmark cases labeled as multi-filing, verify the selected accession set matches the rubric and comparison mode is recorded.

**Acceptance Scenarios**:

1. **Given** a year-over-year revenue question (quarterly metric) and a corpus with the latest 10-Q and the prior-year same fiscal quarter 10-Q, **When** the query is processed, **Then** the system selects those two 10-Q accessions and records comparison mode as year-over-year.
2. **Given** a year-over-year question without quarterly metric cues (annual or unspecified), **When** the corpus has at least two 10-Ks, **Then** the system selects the latest two 10-K accessions and records comparison mode as year-over-year.
3. **Given** a quarter-over-quarter comparison question and at least two quarterly filings in the corpus, **When** the query is processed, **Then** the system selects the latest and immediately prior 10-Q accessions and records comparison mode as quarter-over-quarter or equivalent.
4. **Given** a benchmark item that requires multi-filing selection, **When** evaluated on the labeled subset, **Then** at least 80% of those items are classified as multi-filing by the evaluation harness (not single-filing shortcuts).

---

### User Story 3 - Misalignment detection and fail-closed behavior (Priority: P2)

When selected filings imply incompatible fiscal periods (e.g., mixing unrelated quarter ends for a single-period question, or comparing filings that cannot support the stated comparison), the system does not silently proceed with a misleading scope.

**Why this priority**: Prevents confident wrong answers when period math or form types do not line up.

**Independent Test**: Inject misaligned filing combinations and ambiguous queries; assert user-visible failure or narrowed scope with explanation.

**Acceptance Scenarios**:

1. **Given** a single-period query and a candidate set with non-overlapping period ends that cannot satisfy the anchor, **When** macro routing completes, **Then** the system fails closed with a clear error unless exactly one valid anchor filing remains—in which case it narrows, drops comparison intent, and documents the adjustment in the trajectory.
2. **Given** an explicit user-provided period flag that conflicts with natural-language period hints, **When** reconciliation is impossible, **Then** the system fails before retrieval with a message describing the conflict (no silent override of expert flags without documentation in trajectory).

---

### User Story 4 - Durable trajectory for every query (Priority: P1)

Operators and evaluators auditing a run can see which filings were chosen, how periods were interpreted, what comparison mode applied, and why—without re-running the query.

**Why this priority**: Constitution requires traceability; macro decisions are the root of grounding.

**Independent Test**: Execute representative queries and inspect persisted trajectory artifacts for required macro fields.

**Acceptance Scenarios**:

1. **Given** any successful or failed ask run, **When** the trajectory is retrieved, **Then** it includes selected accession identifiers (or explicit empty set), comparison mode, temporal anchor summary, and a human-readable rationale for the binding decision.
2. **Given** a pre-bound filing set from explicit CLI scope, **When** macro routing skips autonomous selection, **Then** the trajectory still records that the set was pre-bound, lists those accessions, and states the skip reason.

---

### User Story 5 - Benchmark filing-set accuracy (Priority: P2)

The product owner runs an evaluation pass on a FinAgentBench-style labeled subset where expected filing bindings are defined per item. Results report filing-set agreement rate separately from answer correctness.

**Why this priority**: User-defined success metric (70% rubric agreement) requires a repeatable evaluation gate.

**Independent Test**: Run the labeled subset end-to-end; compute filing-set match rate against `expected_bindings` in benchmark cases.

**Acceptance Scenarios**:

1. **Given** the labeled subset where at least 80% of items require multi-filing selection per rubric metadata, **When** the harness classifies macro outcomes, **Then** at least 80% of items are confirmed multi-filing cases (not mis-tagged as single-filing).
2. **Given** the same subset, **When** autonomous macro routing selects filings, **Then** at least 70% of items match the benchmark rubric’s expected accession set (order-insensitive, exact set match).

---

### Edge Cases

- Corpus has only one quarterly filing but the query asks for “prior quarter”: fail closed with guidance to materialize more history or narrow the question.
- Issuer fiscal calendar differs from calendar quarters (e.g., September year-end): mapping uses manifest fiscal labels and period ends, not calendar assumptions alone.
- Query mentions multiple periods (“Q3 2024 and Q2 2024”): bind both if present; misalignment if one is missing from corpus.
- Comparison query with only one eligible filing in corpus: fail closed (do not proceed with a comparison); if the query also states a single-period anchor, narrow to that one filing only with comparison intent removed and rationale recorded.
- YoY quarterly metric but prior-year same fiscal quarter 10-Q absent from corpus: fail closed with message to materialize more history (no fallback to sequential prior quarter unless user rephrases).
- QoQ requested but only one 10-Q in corpus: fail closed with guidance to materialize more quarterly history.
- Query mixes QoQ and YoY cues ambiguously: fail closed and ask for clearer period intent unless LLM proposal passes validator with a single unambiguous comparison mode.
- Mock or fixture corpora with sparse manifests: routing uses manifest truth only; no invented filings.
- Non-English period phrases (“last fiscal year”): supported where a defined phrase catalog maps to anchors; unknown phrases fail closed with suggested rephrasing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST perform macro routing (filing set and temporal scope selection) before section-level or chunk-level navigation for every ask query.
- **FR-002**: System MUST interpret natural-language temporal intent via an assisted macro planner that **proposes** form types, reporting periods, comparison mode, and candidate accessions. A **deterministic validator** MUST approve the proposed binding against manifest facts and pairing rules (including YoY defaults) before retrieval; if validation fails, the system MUST fail closed with an explicit message (no unvalidated LLM binding).
- **FR-003**: System MUST filter the active filing set so retrieval and synthesis use only the selected accession(s), excluding unrelated filings in the same snapshot.
- **FR-004**: System MUST detect fiscal-period misalignment among candidate or selected filings (incompatible anchors, missing comparison partner, or period label mismatch). **Default: fail closed** with an explicit user-visible message. Narrowing is permitted only when a single valid anchor filing remains after removing incompatible candidates; comparison intent MUST be dropped or downgraded and the adjustment MUST be documented in the trajectory rationale.
- **FR-005**: System MUST persist for every query a durable trajectory record containing: selected accession list, comparison mode, temporal anchor summary, and a rationale explaining the binding decision (including pre-bound and fallback paths).
- **FR-006**: System MUST honor explicit user-provided temporal scope (period labels, anchors, compare lists, accessions) when supplied, with defined precedence over natural-language inference; irreconcilable conflicts MUST fail before retrieval.
- **FR-007**: System MUST support multi-filing selection when the query or comparison mode requires it, with at least two distinct accessions when a comparison is requested and the corpus provides them. For **year-over-year** intent: if the query implies a **quarterly metric**, bind the latest 10-Q and the 10-Q for the **same fiscal quarter one year earlier** (fail closed if missing); if **annual or unspecified**, bind the **latest two 10-Ks** (fail closed if fewer than two). For **quarter-over-quarter** intent: bind the **latest 10-Q and the immediately prior 10-Q** by period end (fail closed if fewer than two quarterly filings exist).
- **FR-008**: System MUST expose macro routing outcomes in operator-facing trace output (console or equivalent) consistent with trajectory content so live debugging does not require opening separate audit stores.
- **FR-009**: System MUST provide an evaluation harness entry point that scores filing-set agreement against labeled `expected_bindings` on an in-repo **FinAgentBench macro-routing slice** (extended registry entries plus aligned temporal benchmark cases, minimum 50 labeled items with `multi_filing_required` metadata), independent of final answer text.
- **FR-010**: System MUST NOT emit a SUCCESS retrieval outcome when macro binding failed closed unless the user query is explicitly answered with a scope error message (no fabricated financial figures).

### Key Entities

- **Temporal intent**: Interpreted anchor(s), comparison mode, and optional named fiscal periods derived from query and flags.
- **Filing binding**: The ordered set of selected filings (accession, form type, period end, fiscal label) active for the query.
- **Macro plan**: Intent summary, temporal scope, and rationale produced by macro routing for downstream nodes and trajectory (includes LLM proposal fields and validator pass/fail reason).
- **Binding validation result**: Approved accessions, comparison mode, and validator notes (or failure codes) after deterministic checks on the LLM proposal.
- **Misalignment report**: Structured reason codes (e.g., missing prior quarter, incompatible compare pair) when validation fails or scope is narrowed.
- **Benchmark case**: Labeled query, expected accession set, fiscal periods, and multi-filing flag for evaluation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the designated FinAgentBench-style labeled subset, at least **80%** of items are categorized as requiring multi-filing selection per rubric metadata (harness verification, not model self-report).
- **SC-002**: On the same subset, autonomous macro routing selects the same accession set as the benchmark rubric in at least **70%** of items (exact set match, order not significant).
- **SC-003**: **100%** of ask runs in the evaluation pass include trajectory fields for selected filings, comparison mode, and rationale (audited sample of at least 50 runs).
- **SC-004**: For injected misalignment test cases (minimum 10 scenarios), **100%** produce either fail-closed messages or documented narrow-scope adjustments with no silent use of incompatible filings.
- **SC-005**: Analysts can identify why a filing set was chosen for a query in under **30 seconds** using trajectory or trace output alone (timed usability check on 5 representative queries).

## Assumptions

- A multi-filing materialized corpus per issuer already exists (prior multi-filing corpus capability); this feature enhances how queries bind to it, not initial ingestion.
- Fiscal period metadata in the corpus manifest is authoritative for anchor resolution.
- Evaluation labels are maintained by **extending the in-repo FinAgentBench registry** (and compatible temporal benchmark cases), not an external-only dataset; each macro eval item includes `expected_bindings`, optional `fiscal_periods`, and `multi_filing_required` for SC-001/SC-002 (minimum 50 items).
- Explicit CLI temporal flags remain supported for power users and regression tests; natural-language routing is the default when flags are absent.
- Phrase catalog for temporal mapping is English-first for v1; additional locales are out of scope unless added later.
- Macro routing uses an **LLM-first proposal** with **mandatory deterministic validation**; phrase-catalog shortcuts may exist for efficiency but cannot bypass validation. Benchmarks and unit tests MUST assert validator outcomes independently of LLM wording variance where proposals are stubbed.

## Dependencies

- Multi-filing snapshot manifests with filing references, period ends, and fiscal labels.
- Existing ask pipeline, trajectory persistence, benchmark runner infrastructure, and **FinAgentBench** registration in the 001 benchmark registry.
- Prior temporal-scope contracts for CLI flag precedence and pre-bound filing handoff.
