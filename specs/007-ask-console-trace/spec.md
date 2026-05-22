# Feature Specification: Ask Console Trajectory Trace

**Feature Branch**: `007-ask-console-trace`

**Created**: 2026-05-22

**Status**: Draft

**Input**: User description: "Add comprehensive, beautified console trajectory tracing for `uv run agent-query ask` so operators can follow the full agent execution in the terminal without opening MLflow first. Capture LLM routing, macro/meso/micro graph stages, all LLM I/O, and retrieval decisions—with guarantees that future routing/extraction changes automatically require trace updates."

## Clarifications

### Session 2026-05-22

- Q: Where should console trace text be written relative to the answer? → A: **Trace on stderr; answer and `--json` on stdout** — operators can pipe or redirect the answer/JSON stream without trace noise; trace remains visible on the terminal via stderr.
- Q: When should trace sections appear during an ask run? → A: **Streaming per stage** — each stage section is rendered on stderr when that stage completes, with an optional final summary footer after the graph finishes.
- Q: Where and how does `--trace-json` emit machine-readable trace? → A: **JSONL on stderr** — one serialized trace event object per line, streamed as stages complete; stdout remains answer-only (or `--json` payload only).
- Q: What is the default `--trace` level outside an interactive terminal? → A: **`quiet` on non-TTY**, with **`AGENT_QUERY_TRACE`** env var (`quiet` | `normal` | `verbose`) overriding the default; explicit CLI `--trace` always wins over env.
- Q: Should a separate consolidated “chain-of-thought” narrative appear? → A: **Per-stage decision summaries only** — no extra consolidated narrative paragraph; reasoning is shown only via structured per-stage summaries and fields (no invented prose).
- Q: How do we prevent console trace from drifting when routers or extractors change? → A: **Registry + structured trace events** — each ask-graph stage emits standardized trace events into agent state; console rendering is registry-driven; **automated contract checks** fail CI when graph stages or traceable decision fields lack coverage.
- Q: Should trace duplicate routing logic for pretty messages? → A: **No** — display text is derived from the same structured fields persisted for audit (intent, plan, evidence, traversal); formatters must not re-run ranking or classification for display.
- Q: What triggers a mandatory trace update when code changes? → A: Any change to ask-graph stage list, stage decision outputs, or audit trajectory fields **must** update the trace registry and pass registry contract checks in the same change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stage-by-Stage Console Trace (Priority: P1)

A developer runs `agent-query ask` with `--trace normal` and sees a beautified, sectioned console trace of each ask-graph stage with timings and one-line decision summaries, without opening MLflow.

**Why this priority**: Core operator value when debugging routing or evidence selection.

**Independent Test**: Run ask with mock LLM and fixture ingestion; verify console shows every ask stage in execution order with decision summaries.

**Acceptance Scenarios**:

1. **Given** `--trace normal`, **When** each ask-graph stage completes, **Then** that stage’s trace section appears on stderr before the next stage runs; after success, every stage has been shown in execution order.
2. **Given** `--trace quiet`, **When** ask completes, **Then** console output matches pre-feature minimal output (answer plus status block only).
3. **Given** `--json` without `--trace-json`, **When** ask completes, **Then** stdout contains only the JSON payload (no trace sections) and trace content (if any) appears only on stderr.

---

### User Story 2 - LLM Routing & Full LLM I/O Visibility (Priority: P2)

The trace shows intent classification (automated vs keyword fallback), macro planning when applicable, and every language-model call in the ask path (prompt previews, response previews, model identity, latency).

**Why this priority**: User requires visibility into routing logic and all local or judge model interactions.

**Independent Test**: Run with mock LLM; verify intent section shows fallback annotation and synthesis section labels non-live path.

**Acceptance Scenarios**:

1. **Given** successful LLM intent classification, **When** trace renders, **Then** intent label, classification source, applied source bias, and truncated prompt/response appear.
2. **Given** keyword fallback, **When** trace renders, **Then** fallback reason is visible and classification source is not mislabeled as LLM.
3. **Given** `--trace verbose`, **When** synthesis runs, **Then** system and user prompt bodies appear truncated per configuration limits.

---

### User Story 3 - Extraction & Retrieval Decision Trail (Priority: P3)

The trace explains filing binding, section selection, evidence filtering and ranking, graph traversal visits, and synthesis context limits applied before the final answer.

**Why this priority**: Connects console output to what information was retrieved and why.

**Independent Test**: Qualitative ask on a pilot issuer; trace shows narrative-biased evidence lines and bound filing identifiers in the macro section.

**Acceptance Scenarios**:

1. **Given** qualitative intent, **When** evidence extraction runs, **Then** trace states applied source bias and evidence counts before and after filtering.
2. **Given** a pre-bound filing set from temporal resolution, **When** macro stage runs, **Then** trace notes pre-bound path and lists bound accessions without unnecessary replanning.
3. **Given** graph traversal records populated, **When** trace renders, **Then** visits appear in execution order with stage and node identifiers.

---

### User Story 4 - Trace Stays in Sync When Graph Evolves (Priority: P1)

When a developer adds, removes, or reorders ask-graph stages or changes router or extractor decision outputs, automated checks fail until trace registry and contract tests are updated—console trace cannot silently fall behind production logic.

**Why this priority**: Future routing and extraction changes must automatically trigger trace updates.

**Independent Test**: Introduce an unregistered stage in a test fixture; registry contract check must fail with an explicit missing-stage message.

**Acceptance Scenarios**:

1. **Given** a new ask-graph stage added, **When** CI runs without registry update, **Then** build fails naming the missing stage.
2. **Given** a new decision field on intent or evidence records, **When** schema contract runs without registry bump, **Then** CI fails listing uncovered fields.
3. **Given** extractor logic changes filter rules, **When** the stage emits updated trace events, **Then** console reflects new fields without duplicating filter logic in the formatter.

---

### Edge Cases

- Mock LLM or keyword fallback: trace annotates non-LLM paths clearly.
- Context overflow retry on synthesis: trace shows retry with tightened limits when applicable.
- Empty evidence or insufficient answer: trace shows sufficiency path before short answer.
- Non-color terminals: readable plain-text fallback.
- Piped stdout (`ask ... | jq`): stderr still receives trace when `--trace` is not `quiet`; stdout stays answer/JSON-only.
- `--trace-json` with piped stdout: JSONL trace lines on stderr only; scripts capture via `2> trace.jsonl` without polluting jq input.
- Very large prompts: truncation with omitted-character counts per configuration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `agent-query ask` MUST accept `--trace {quiet,normal,verbose}`. Default: `normal` when stderr is a TTY, `quiet` otherwise. **`AGENT_QUERY_TRACE`** MAY set the default (`quiet` | `normal` | `verbose`) before the TTY heuristic is applied. Explicit CLI `--trace` MUST override both env and TTY defaults.
- **FR-002**: Console trace MUST NOT alter routing, extraction, or answer outcomes (observability only).
- **FR-003**: Trace output MUST use structured sections (headers, consistent labels, optional color when supported) and MUST be written to **stderr**; the answer text and `--json` payload MUST remain on **stdout** only.
- **FR-004**: Every ask-graph stage MUST emit standardized **trace events** appended to agent state via a shared mechanism; stages MUST NOT print trace content through ad-hoc CLI calls embedded in business logic.
- **FR-004a**: For `--trace normal` and `--trace verbose`, the console reporter MUST **stream** each stage’s formatted section to stderr immediately when that stage completes; a brief final summary (total duration, status, citation count) MAY follow on stderr after synthesis.
- **FR-004b**: Trace MUST NOT emit a separate consolidated “chain-of-thought” narrative paragraph; operator reasoning visibility is limited to **per-stage `decision_summary` lines** and structured fields (intent, plan, evidence previews, traversal), derived from audit state without invented text.
- **FR-005**: A central **ask trace registry** MUST map each stage identifier to display metadata and a formatter that renders trace events plus relevant state fields for console output.
- **FR-006**: The set of registry stage identifiers MUST match the ask execution graph stage list exactly; an automated contract check MUST fail on any mismatch.
- **FR-007**: Console formatters MUST render from trace events and typed agent state (intent record, macro plan, filing set, traversal visits, evidence list) and MUST NOT re-implement ranking, filtering, or intent classification for display, and MUST NOT synthesize free-form chain-of-thought prose beyond per-stage summaries.
- **FR-008**: All language-model calls in the ask path MUST pass through a shared traced invocation helper that records stage name, model settings, truncated messages, truncated completion, latency, and errors as trace events.
- **FR-009**: Console intent section MUST mirror persisted intent router audit fields (intent label, source, bias, fallback reason, model identity, latency).
- **FR-010**: Macro, meso, and micro sections MUST include decision summaries built from the same structures written to the durable trajectory record.
- **FR-011**: `--json` mode MUST remain unchanged on stdout; when `--trace-json` is set, trace events MUST be emitted as **JSONL on stderr** (one JSON object per line, streamed per stage). Human-readable trace sections and JSONL MAY both appear on stderr when `--trace` is not `quiet` and `--trace-json` is set.
- **FR-012**: Existing MLflow trajectory and intent artifacts MUST remain; console trace is a complementary human-readable projection.
- **FR-013**: Truncation limits for prompts and excerpts MUST be configurable (environment or dedicated trace configuration).

### Trace Coupling & Evolution (NON-NEGOTIABLE)

- **FR-014**: **Single registration point** — all ask-graph stages and language-model touchpoints MUST register in the ask trace registry; adding a stage without registration is a build-breaking defect.
- **FR-015**: **Registry contract gate** — automated tests MUST compare ask-graph stages to registry keys, validate registered trace event types, and validate observability-related agent state fields referenced by renderers.
- **FR-016**: **Schema drift gate** — automated tests MUST detect additions or removals of trace-relevant fields on intent, plan, and evidence records without a registry schema version bump.
- **FR-017**: **No orphan observability state** — new agent state fields intended for debugging MUST either emit a trace event or be mapped in the registry for that stage; contract tests enforce coverage.
- **FR-018**: **Change protocol** — modifications to ask routing or extraction logic MUST update trace event payloads in the same change; golden console snapshots for at least one numeric and one qualitative pilot query MUST be updated when visible output changes.
- **FR-019**: **CI policy** — pull requests touching ask orchestration stages MUST run trace registry contract tests.

### Key Entities

- **Trace event**: Atomic observability record (stage, event type, timestamp, duration, payload, optional language-model I/O sub-record).
- **Ask trace registry**: Maps stage identifier to display metadata, schema version, and formatter.
- **Agent trace event list**: Append-only collection during ask execution; the console reporter streams formatted sections to stderr per stage and may emit a final summary after the run.
- **Trajectory record** (existing): Durable audit store; console output MUST remain consistent with fields persisted for MLflow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `--trace normal`, **100%** of ask-graph stages appear in console output in correct order on a pilot set of 10 queries (mock and live).
- **SC-002**: With `--trace quiet`, pilot replays produce the same minimal footer fields as the pre-feature baseline (answer text may differ by model).
- **SC-003**: An unregistered ask-graph stage in a test fixture fails automated checks in under one second with a message naming the missing stage.
- **SC-004**: For qualitative and numeric pilot asks, an external reviewer identifies intent, filing binding, evidence bias, and top evidence count from console trace alone in **≥ 95%** of cases.
- **SC-005**: Wall-clock overhead with `--trace quiet` is **< 5%** versus baseline on mock runs.
- **SC-006**: `--json` without `--trace-json` produces byte-stable JSON structure (no trace keys) on stdout in fixture replay tests.
- **SC-007**: With `--trace-json`, stderr JSONL lines parse as valid trace event objects and include at least one line per completed ask-graph stage on pilot runs.

## Assumptions

- Ask execution remains a linear stage pipeline unless changed with registry updates (macro planning → intent classification → meso routing → micro extraction → answer synthesis).
- Operators use modern terminals that support optional color; plain fallback is required.
- CI and scripts without a TTY default to `quiet` unless `AGENT_QUERY_TRACE` or `--trace` is set.
- Durable MLflow artifacts remain the audit source of record; console is for interactive debugging.
- Benchmark judge calls are out of ask CLI scope unless explicitly invoked by the same command in a later iteration.

## Out of Scope

- Replacing MLflow or building a web dashboard.
- Tracing materialize or ingestion pipelines in v1.
- Logging raw SEC filing bodies to the console.
- Storing full prompts in MLflow by default (verbose optional artifact only).
