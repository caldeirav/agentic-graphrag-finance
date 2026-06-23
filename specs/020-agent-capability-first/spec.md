# Feature Specification: Agent Capability-First Numeric Synthesis

**Feature Branch**: `019-agent-failure-investigation` (spec `020-agent-capability-first`)

**Created**: 2026-06-22

**Status**: In Progress

**Input**: Improve graph-full performance on primary-evidence XBRL stratum (26 items, task_success=0, MRR≈0.96) by strengthening agent capabilities—prompts, structured output contracts, temporal binding, and LLM-guided XBRL fact resolution—rather than expanding keyword-based deterministic synthesis handlers. Codify as constitution Principle VII and a Cursor rule. Provide frozen XBRL numeric cohort for fast iteration before full paper-v1.1 repro.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structured Numeric Answers (Priority: P1)

A benchmark operator running graph-full on XBRL-stratum items receives agent answers that state one metric, value, unit, and fiscal period with citations—not raw evidence chunk lists.

**Why this priority**: 69% of XBRL-stratum failures are template-style chunk dumps despite high retrieval.

**Independent Test**: Run cohort-debug on `xbrl_numeric_cohort.json`; zero answers match the chunk-dump pattern.

**Acceptance Scenarios**:

1. **Given** ranked XBRL evidence and a numeric financebench question, **When** synthesis completes in live mode, **Then** the answer text does not begin with "Based on N evidence chunk(s)".
2. **Given** a structured synthesis response, **When** rendered for the user, **Then** the first sentence contains a definitive numeric or ratio claim with period context.
3. **Given** USE_MOCK_LLM=1 (CI), **When** synthesis runs, **Then** deterministic shortcuts remain available for regression fixtures.

---

### User Story 2 - Temporal Filing Binding (Priority: P1)

When a question references FY2025 or a specific fiscal period, the macro router binds the annual 10-K (or stated quarter) rather than the latest filing in the corpus.

**Why this priority**: 54% of XBRL-stratum answers cite wrong period (2026/Q1 vs FY2025 in question).

**Independent Test**: Cohort items with explicit FY2025 in the question must not cite 2026-only periods in the answer when FY2025 filing is in the bound set.

**Acceptance Scenarios**:

1. **Given** benchmark metadata includes `fiscal_periods: ["2025"]`, **When** macro routing runs, **Then** the macro planner prompt includes that fiscal hint.
2. **Given** a question "for fiscal year 2025", **When** multiple filings exist, **Then** synthesis instructions prefer evidence whose period ends in 2025.

---

### User Story 3 - LLM-Guided XBRL Fact Resolution (Priority: P2)

For numeric questions with multiple XBRL facts in evidence, the agent uses an LLM skill to select the fact(s) that match the question metric before synthesis—not keyword routing to a single concept.

**Independent Test**: Unit test with mocked LLM selecting correct fact index from a list; integration test on 3 cohort items.

**Acceptance Scenarios**:

1. **Given** multiple XBRL excerpts in evidence, **When** the resolution skill runs, **Then** it returns selected chunk ids and a short rationale in the trajectory.
2. **Given** a ratio question (debt-to-equity), **When** resolution runs, **Then** the skill may select multiple facts or indicate computation—not a unrelated line item.

---

### User Story 4 - XBRL Numeric Cohort Gate (Priority: P2)

An engineer validates synthesis fixes on the frozen 26-item XBRL cohort before full reproduction.

**Acceptance Scenarios**:

1. **Given** `xbrl_numeric_cohort.json`, **When** `repro cohort-debug` runs, **Then** all 26 items execute with structured trace summaries.
2. **Given** cohort metrics, **When** compared before/after a fix, **Then** chunk-dump share and mean value_alignment are reported.

---

### User Story 5 - Capability-First Governance (Priority: P3)

Contributors follow Principle VII: prefer prompts/tools/skills over new deterministic question-type handlers.

**Acceptance Scenarios**:

1. **Given** the updated constitution, **When** a contributor proposes a new `_try_synthesize_*` handler, **Then** ADR or plan exception is required.
2. **Given** the Cursor rule, **When** editing `src/retrieval/synthesis.py`, **Then** agent-capability-first guidance is visible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Live synthesis MUST use structured answer contract (JSON schema → rendered prose) as the primary path for non-qualitative queries.
- **FR-002**: Live synthesis MUST NOT emit template chunk-dump answers; retry structured synthesis once, then abstain with explicit insufficiency.
- **FR-003**: Deterministic synthesis shortcuts (`_try_synthesize_*` ladder) MUST run only when `USE_MOCK_LLM=1`.
- **FR-004**: Macro planner MUST receive benchmark fiscal period hints and temporal anchor from evaluation metadata.
- **FR-005**: XBRL fact resolution skill MUST use LLM selection over structured evidence metadata (concept, period, value).
- **FR-006**: Repository MUST ship `xbrl_numeric_cohort.json` (26 item ids) under quality-v2.0.1 draft.
- **FR-007**: Constitution MUST add Principle VII (Capability-First Agent Design).
- **FR-008**: Cursor rule `agent-capability-first.mdc` MUST document the decision ladder.

### Success Criteria

- **SC-001**: Chunk-dump answers on XBRL cohort drop from 18/26 to ≤2/26 in a local cohort-debug run (operator-measured).
- **SC-002**: Mean value_alignment on XBRL stratum improves by ≥0.15 vs repaired paper-v1.1 baseline (0.0).
- **SC-003**: No new keyword-based `_try_synthesize_*` handlers added in this feature.

## Assumptions

- External Gemini judge remains the scoring authority; no deterministic VA override.
- paper-v1.0 / v2.0.0 locks stay immutable.
- Full 200×5 repro is out of scope; cohort-debug validates fixes.

## Out of Scope

- Replacing the external judge
- Publishing v2.0.1 bundle
- Removing all legacy deterministic handlers (mock/CI only)
