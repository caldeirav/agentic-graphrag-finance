# Feature Specification: Graph-Native Meso and Micro Agentic Navigation

**Feature Branch**: `009-graph-native-meso-micro`

**Created**: 2026-05-23

**Status**: Draft

**Input**: Replace heuristic-only meso and micro routing with graph-native agentic navigation: the agent must traverse structural and temporal edges from the macro-selected filing set to rank sections, then follow containment, footnote, cross-reference, and table-row edges to extract evidence chunks. Meso and micro stages must emit node and edge identifiers visited (not only flat lists). The agent must support multi-hop paths (e.g., section → table → footnote → related paragraph). Answers must remain grounded only in retrieved chunks. Success: trajectory records and console trace include edge types traversed and allow users to identify the content considered by the agent, and its decisions; on an internal gold-path test set, at least 75% of required evidence chunks are reached without scanning the entire graph.

## Clarifications

### Session 2026-05-23

- Q: What is the meso/micro navigation control model (who chooses each hop)? → A: LLM proposes each next hop (or small candidate set); a deterministic validator enforces edge catalog, macro scope, budgets, and fail-closed stops before advancing.
- Q: Which edge types may the agent traverse during meso/micro navigation? → A: Structural edges only (containment, sequential order, footnote, cross-reference within the macro-bound filing set). Temporal-transition and semantic-similarity edges are out of scope for agent hops; multi-filing comparison navigates each bound filing via structural paths from its document root.
- Q: What counts as “scanning the entire graph” for SC-003 gold-path evaluation? → A: Visiting ≥90% of navigable graph nodes (sections and chunk nodes) within the macro-bound filing set before retrieving the required chunk.
- Q: What happens when graph-native navigation finds no evidence after budget? → A: No heuristic fallback in production; return insufficient-evidence or fail-closed with the partial graph visit trace (no keyword/flat-pool substitution).
- Q: How many meso-ranked sections feed micro extraction? → A: Top 3 sections per bound filing (by meso rank) proceed to micro; lower-ranked sections appear in the visit trace only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Section discovery via disclosure graph (Priority: P1)

An analyst asks a question after macro routing has bound one or more filings. The system navigates the issuer’s disclosure graph starting from each bound filing’s document root—using structural relationships (containment, order, footnote, and cross-reference)—to identify and rank the sections most relevant to the question, rather than applying fixed keyword or section-name heuristics alone.

**Why this priority**: Incorrect or shallow section selection causes missed tables, footnotes, and cross-referenced narrative; graph-native meso routing is the foundation for faithful financial answers.

**Independent Test**: On queries with known target sections in a labeled corpus, compare ranked section outcomes to expert labels and verify navigation stayed within the macro-bound filing set.

**Acceptance Scenarios**:

1. **Given** a macro-bound single-filing scope and a question about a named financial statement or MD&A topic, **When** meso navigation runs, **Then** the system ranks sections by traversing allowed structural edges from the bound document root and records each visited node and edge with its relationship type.
2. **Given** a macro-bound multi-filing scope (e.g., year-over-year comparison), **When** meso navigation runs, **Then** the system navigates each bound filing independently via structural edges from that filing’s document root (no temporal-transition or semantic-similarity hops) and records which filing each ranked section belongs to.
3. **Given** meso navigation completes, **When** an operator inspects the run artifact, **Then** they see an ordered visit trace (node identifiers, edge types, and relationship direction), not only a flat list of section titles.
4. **Given** meso ranks more than three sections in a bound filing, **When** micro extraction runs, **Then** only the top three sections per filing (by meso rank) are micro-navigated; additional ranked sections remain in the meso trace without micro hops.

---

### User Story 2 - Multi-hop evidence extraction (Priority: P1)

An analyst’s question requires evidence that spans structure inside a section—for example, a table row linked to a footnote and a related narrative paragraph. The system follows containment, table-row, footnote, and cross-reference relationships in sequence to collect evidence chunks along explicit paths.

**Why this priority**: Many SEC answers depend on footnote chains and table–text linkage; single-hop or flat chunk retrieval misses required context.

**Independent Test**: On gold-path cases labeled with required chunk identifiers, verify the micro stage reaches those chunks via recorded multi-hop paths (e.g., section → table → footnote → paragraph).

**Acceptance Scenarios**:

1. **Given** a section in the top three per bound filing from meso navigation, **When** micro extraction runs, **Then** the system may traverse multiple hops along allowed structural edges and emits a path record listing each hop’s source node, edge type, and target node.
2. **Given** a question whose answer depends on a footnote referenced from a table, **When** micro extraction runs, **Then** the retrieved evidence includes chunks from both the table context and the linked footnote or cross-referenced paragraph, with the linking edge type visible in the trace.
3. **Given** micro extraction completes, **When** synthesis uses the evidence, **Then** every cited fact or quote maps to a chunk that appears in the micro retrieval set (no content invented beyond retrieved chunks).

---

### User Story 3 - Auditable navigation trace (Priority: P1)

Operators, compliance reviewers, and evaluators need to understand what the agent considered and why—not just the final answer. Each query’s durable trajectory and interactive console trace must expose meso and micro navigation decisions in human-reviewable form.

**Why this priority**: Constitution requires traceability; graph-native routing is only trustworthy if visits and edge types are inspectable.

**Independent Test**: Run representative queries with tracing enabled; confirm trajectory and console output list edge types traversed, visited node identifiers, and enough content pointers for a reviewer to open the underlying disclosure passages.

**Acceptance Scenarios**:

1. **Given** any completed query with tracing enabled, **When** the trajectory artifact is opened, **Then** it includes meso and micro visit records with edge types traversed and stable node identifiers for each step.
2. **Given** the same query with console trace at normal or verbose depth, **When** the user reviews the trace, **Then** they can identify which sections were ranked, which paths were followed, and which evidence chunks were selected for synthesis—without re-running the query.
3. **Given** navigation stops early (budget, dead end, or no further allowed edges), **When** the trace is inspected, **Then** the stop reason is recorded alongside partial visit history.

---

### User Story 4 - Gold-path reachability without full-graph scan (Priority: P2)

The product team maintains an internal gold-path test set: each item specifies required evidence chunks and acceptable navigation paths for a query on a fixed materialized corpus. The system must reach most required chunks efficiently—demonstrating that agentic traversal targets evidence rather than enumerating the whole graph.

**Why this priority**: Validates that graph-native navigation improves precision and cost versus heuristic or exhaustive strategies.

**Independent Test**: Run the gold-path harness on the labeled set; measure the fraction of required chunks reached before any full-corpus enumeration fallback.

**Acceptance Scenarios**:

1. **Given** the internal gold-path test set (minimum 40 labeled items across single- and multi-filing queries), **When** evaluated under fixed corpus and mock or live agent policies, **Then** at least 75% of required evidence chunks are reached without a full-graph scan (defined as visiting ≥90% of navigable nodes in the macro-bound filing set before the required chunk is retrieved).
2. **Given** a gold-path item with a documented acceptable multi-hop pattern, **When** micro navigation succeeds, **Then** the recorded path’s edge-type sequence matches one of the acceptable patterns or an equivalent documented in the item rubric.
3. **Given** a required chunk is not reached, **When** the harness records failure, **Then** the trajectory shows which hops were attempted and where navigation stopped.

---

### Edge Cases

- What happens when macro binding yields a filing set whose graph has no sections matching the question intent? The system records an empty or partial meso trace, fails closed or returns insufficient-evidence with explicit scope—not silent fallback to unrelated filings or heuristic section/chunk pools.
- What happens when meso/micro exhausts the navigation budget without required evidence? The system returns insufficient-evidence or fail-closed with the partial visit trace; it MUST NOT fall back to heuristic keyword ranking or unordered chunk pools in default production runs.
- How does the system handle dead ends (node with no further allowed structural edges)? Navigation stops that branch, records the dead end in the trace, and may explore alternate branches within hop and visit budgets.
- What happens when the graph offers temporal-transition or semantic-similarity edges? Agent meso/micro navigation MUST NOT traverse them; multi-filing scope is enforced by macro binding plus independent structural navigation per bound filing.
- How are hop and visit budgets exceeded? Navigation halts with a documented budget reason; partial evidence may proceed only if grounding rules still allow synthesis from retrieved chunks.
- What happens when the same chunk is reachable by multiple paths? The trace may deduplicate chunks for synthesis but MUST retain at least one full path record per chunk used in the answer.
- How does the system behave if graph materialization is incomplete (missing footnote or cross-reference edges)? Fail closed or insufficient-evidence with trace noting missing linkage—not inferred relationships.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After macro routing establishes the active filing set, meso navigation MUST start from document roots of those filings only and MUST NOT expand scope to unbound accessions.
- **FR-002**: Meso navigation MUST rank sections by agentic traversal over **structural** relationships only: containment, sequential order, footnote linkage, and cross-reference linkage within each macro-bound filing. At each hop, an LLM MUST propose the next hop or a small candidate set; a deterministic validator MUST approve or reject the proposal against the allowed structural edge subset, macro-bound scope, and navigation budget before the visit is recorded. For multi-filing macro scope, meso MUST run structural navigation separately from each bound filing’s document root.
- **FR-002a**: Micro extraction MUST use the same LLM-propose / validator-approve pattern for each hop along structural paths from ranked sections; rejected proposals MUST be recorded in the visit trace with reason codes (no silent skip).
- **FR-003**: Meso navigation MUST emit a visit trace listing, for each step: source node identifier, edge relationship type, and target node identifier; flat section-name lists alone are insufficient.
- **FR-003a**: After meso ranking completes, at most the **top three sections per macro-bound filing** (by meso rank) MUST be handed to micro extraction; lower-ranked sections MUST be recorded in the meso trace but MUST NOT receive micro navigation hops.
- **FR-004**: Micro extraction MUST retrieve evidence by following allowed structural edges: containment (section to table, table to row, section to paragraph), footnote linkage, cross-reference linkage, and sequential order within the same parent where applicable.
- **FR-005**: Micro extraction MUST support multi-hop paths (minimum two hops beyond the section root) when evidence requires chained structure (e.g., section → table → footnote → related paragraph).
- **FR-006**: Micro extraction MUST emit a visit trace with the same node-and-edge identifier requirements as meso, including full path records for each evidence chunk used in synthesis.
- **FR-007**: The system MUST enforce a configurable navigation budget (maximum hops and/or visited nodes per query) and MUST record when the budget stops further traversal.
- **FR-008**: Agent meso and micro navigation MUST NOT traverse temporal-transition or semantic-similarity edge types, even if present in the materialized graph catalog for other purposes (e.g., reachability audit).
- **FR-009**: The validator MUST reject any LLM hop proposal that uses a disallowed edge type or targets a node outside the macro-bound filing set.
- **FR-010**: Synthesis and final answers MUST use only evidence chunks present in the micro retrieval set; numeric and narrative claims MUST be traceable to those chunks.
- **FR-011**: Every completed query MUST persist meso and micro visit traces (including edge types traversed) in the durable trajectory store used for audit and evaluation.
- **FR-012**: Console trace output MUST expose meso and micro navigation at a depth sufficient for a reviewer to identify content considered and navigation decisions, consistent with existing ask-trace conventions.
- **FR-013**: Heuristic-only meso and micro routing (fixed section maps, keyword-only ranking, or unordered chunk pools without graph visits) MUST NOT remain the default production path after this feature ships.
- **FR-013a**: When graph-native navigation yields no evidence chunks (empty meso rank, dead ends, or budget exhausted), the system MUST return insufficient-evidence or fail-closed and MUST NOT substitute heuristic meso/micro retrieval in default production runs; partial visit traces MUST still be persisted.
- **FR-014**: An internal gold-path evaluation harness MUST measure required-chunk reach rate and whether navigation avoided a **full-graph scan**, defined as visiting ≥90% of navigable graph nodes (sections and chunk nodes) within the macro-bound filing set before the required chunk is retrieved; harness output MUST record visit counts and the scan ratio per item.
- **FR-015**: Evaluation harness results for the gold-path set MUST be reproducible on a fixed materialized corpus snapshot and suitable for regression gating in continuous integration.

### Key Entities

- **Macro-bound filing set**: The accessions and comparison context selected before meso/micro navigation; defines the legal scope for all graph traversal.
- **Disclosure graph node**: A typed unit in the materialized filing graph (document, section, table, row, paragraph, or structured fact) with a stable identifier.
- **Disclosure graph edge**: A typed directed relationship between nodes governed by the edge catalog; **agent-allowed edges** are the structural subset (containment, sequential order, footnote, cross-reference) used for meso/micro hops.
- **Navigation visit**: One traversed step: source node, edge type, target node, and optional stop or budget metadata.
- **Navigation path**: An ordered sequence of visits from a meso or micro root to an evidence chunk.
- **Evidence chunk**: A retrieval unit attached to a graph node, eligible for synthesis and citation.
- **Gold-path test item**: A labeled query, bound filing context, required chunk identifiers, optional acceptable path patterns, and rubric for pass/fail.
- **Meso/micro trajectory segment**: Durable record of ranked sections, extracted chunks, visit traces, edge types, and stop reasons for one query run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On 100% of completed traced queries, durable trajectory artifacts include meso and micro visit records with edge types traversed and stable node identifiers for each navigation step.
- **SC-002**: In a structured usability review of at least five representative queries, reviewers can identify the sections considered, paths followed, and evidence chunks used for the answer from console trace and trajectory alone, without re-execution (target: pass all five reviews).
- **SC-003**: On the internal gold-path test set (minimum 40 items), at least **75%** of required evidence chunks are reached without a full-graph scan per item (scan = visiting ≥90% of navigable nodes in the macro-bound filing set before the required chunk is retrieved).
- **SC-004**: On the same gold-path set, at least **90%** of runs that reach a required chunk record a navigation path whose edge-type sequence matches the item rubric or an documented equivalent pattern.
- **SC-005**: In automated grounding checks on the gold-path subset, **100%** of synthesized claims that reference filing content map to chunks present in the micro retrieval set (zero ungrounded content references in evaluated items).

## Assumptions

- Macro routing (filing set and temporal scope) is provided by the existing autonomous macro capability; replacing macro logic is out of scope.
- Filing graphs are materialized with preserved structure and a published edge-type catalog; agent traversal uses only the structural subset (containment, footnote, cross-reference, order)—not temporal-transition or semantic-similarity links.
- Meso ranks sections; micro selects evidence chunks along paths from the top three sections per bound filing—responsibilities remain layered but both use graph-native navigation with LLM-proposed hops and deterministic validation (aligned with autonomous macro routing).
- Default navigation budgets are set conservatively to prevent runaway traversal; exact limits are defined during planning, not in this spec.
- The gold-path test set is maintained in-repo with expert labels on a fixed issuer corpus snapshot (similar to other FinAgentBench-style slices); initial minimum size is 40 items with room to grow.
- Full-graph enumeration may exist only as an explicit diagnostic or evaluation fallback and MUST NOT count toward SC-003 success when used. A run counts as a full-graph scan when ≥90% of navigable nodes in the macro-bound set are visited before the labeled required chunk is reached.
- Production `ask` flows do not use heuristic meso/micro fallback on graph-navigation failure; diagnostic tooling may document alternate modes separately in planning contracts.
- Live LLM-guided navigation and mock/fixture navigation for CI are both supported, but success metrics are measured on the labeled harness under agreed environment flags documented in the evaluation contract.
- Console trace depth and field naming align with the existing ask-trace feature so operators have one coherent audit story across macro, meso, and micro stages.

## Dependencies

- Autonomous macro routing and multi-filing corpus scope (prior features).
- Graph materialization with structural edge preservation and edge-type catalog.
- Durable trajectory and console trace infrastructure for query runs.
- Independent evaluation layer capable of gold-path regression without importing retrieval orchestration internals.
