# Feature Specification: Docling-Graph Knowledge Materialization

**Feature Branch**: `004-docling-graph-materialization`

**Created**: 2026-05-21

**Status**: Draft

**Input**: User description: "Specify knowledge-graph materialization from Docling-parsed SEC XBRL filings using docling-graph: document, section, table, row, paragraph, and XBRL fact nodes with typed edges for structural containment, reading order, footnote attachment, cross-references between chunks, temporal transitions across filings for the same issuer, and semantic similarity links between related chunks (e.g., same concept across periods or co-mentioned risk themes). Agent must be able to traverse from a document node to any cited evidence chunk via documented edge types. Parsing must remain XBRL-primary; graph building must fail closed when mandatory structural links cannot be represented. Success: 95% of audited numeric facts in a pilot corpus are reachable via a documented path of at most N hops from the document root."

## Clarifications

### Session 2026-05-21

- Q: What is the maximum hop count (N) for reachability success? → A: Pilot audit uses **N = 6** as the default hop budget from document root to evidence chunk; the budget is recorded in audit artifacts and may be tightened after baseline measurement.
- Q: Which semantic-similarity linking strategy should v1 use? → A: **Hybrid** — deterministic cross-period links for the same XBRL concept identity (with period metadata); optional embedding-based thematic links for narrative risk co-mention only above a documented threshold.
- Q: Which edge types count toward the 95% reachability audit shortest path? → A: **Structural only** — containment, reading order, footnote attachment, and cross-reference; temporal and semantic-similarity edges are excluded from audit paths.
- Q: When XBRL fact instances exceed indexing limits, what inclusion policy applies? → A: **No cap** — materialize every parsed XBRL fact instance (all period contexts) into the graph; accept larger snapshots rather than silently dropping facts.
- Q: How should docling-graph relate to the existing custom graph builder? → A: **Replace** — docling-graph is the sole materialization engine; the legacy custom builder is retired or reduced to a thin adapter after parity tests.
- Q: What should the pilot reachability audit population include? → A: **XBRL fact nodes plus material table-row numerics**, using a **stratified sample of at least 100** facts across pilot filings.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structurally Faithful Graph from XBRL-Primary Filings (Priority: P1)

A financial analyst or retrieval agent needs each ingested SEC filing represented as a navigable knowledge graph—not a flat index—so that tables, narrative sections, footnotes, and numeric facts retain their relationships. After standard XBRL-primary parsing produces structured sections and tables, graph materialization creates typed nodes (document, section, table, row, paragraph, XBRL fact) and mandatory structural edges (containment, reading order, footnote attachment, cross-references between chunks) so every evidence chunk is anchored to its source document.

**Why this priority**: Without faithful structural graphs, agentic retrieval cannot cite or traverse disclosures reliably; this is the foundation for grounded answers.

**Independent Test**: Materialize a graph for one 10-K and one 10-Q from the pilot corpus; verify every table row and indexed XBRL fact node has a containment path to the document root and that reading-order edges connect sequential sections within the filing.

**Acceptance Scenarios**:

1. **Given** a validated XBRL-primary parsed filing, **When** graph materialization runs, **Then** the snapshot includes exactly one document node per filing and child nodes for every materialized section, table, row, paragraph, and XBRL fact intended for retrieval.
2. **Given** a table with multiple rows in the parsed structure, **When** materialization completes, **Then** each row is represented as a row node linked to its parent table and section via containment edges.
3. **Given** a footnote reference in narrative or tabular content, **When** the target footnote exists in the parse, **Then** a footnote-attachment edge links the referring chunk to the footnote chunk; when the target is missing, **Then** materialization records an explicit unresolved-reference status for that filing.
4. **Given** a cross-reference between two in-filing chunks, **When** both endpoints resolve, **Then** a cross-reference edge connects them and both remain reachable from the document node.
5. **Given** mandatory structural links cannot be created for a filing (e.g., document node would have zero section children), **When** materialization is attempted, **Then** the system fails closed for that filing, excludes it from the published snapshot, and records a failure reason—without silently publishing a broken graph.

---

### User Story 2 - Issuer-Level Temporal and Semantic Linking (Priority: P2)

An analyst comparing periods or themes across filings needs edges that connect related chunks beyond a single document. For the same issuer, materialization adds temporal-transition edges between filings ordered by reporting period, and semantic-similarity edges between related chunks (e.g., the same financial concept across quarters or co-mentioned risk themes) so agents can move from one period’s evidence to another without re-parsing raw text.

**Why this priority**: Multi-period financial questions depend on explicit cross-filing linkage; structural in-filing graphs alone are insufficient.

**Independent Test**: Materialize a multi-filing issuer snapshot with at least four quarterly reports and one annual report; verify temporal-transition edges exist between consecutive period document nodes and that at least one semantic-similarity edge connects matching revenue-related XBRL facts across two periods.

**Acceptance Scenarios**:

1. **Given** multiple filings for one issuer in a snapshot, **When** materialization completes, **Then** temporal-transition edges connect document nodes in reporting-period order with direction and period metadata preserved on the edge.
2. **Given** the same XBRL concept reported in two periods with distinct fact nodes, **When** deterministic similarity linking runs, **Then** a semantic-similarity edge connects the pair by concept identity and carries period labels sufficient for audit (no embedding required).
3. **Given** narrative chunks that share a co-mentioned risk theme above a documented embedding similarity threshold, **When** optional thematic linking runs, **Then** semantic-similarity edges may connect them; these edges are supplementary and MUST NOT be the only path used to satisfy primary numeric grounding audits.
4. **Given** a single-filing snapshot, **When** materialization completes, **Then** temporal-transition edges are omitted and the snapshot status documents single-filing mode.

---

### User Story 3 - Agent Traversability and Citation Paths (Priority: P3)

During retrieval, the agent must start from a bound document node and reach any cited evidence chunk using only documented edge types, so citations can be explained as a path (e.g., document → section → table → row, or document → XBRL facts section → fact). Operators and benchmarks audit those paths for grounding.

**Why this priority**: Traversability is the operational definition of “grounded evidence”; undocumented shortcuts undermine trust.

**Independent Test**: Draw a stratified sample of at least **100** numeric facts (XBRL fact nodes and material table-row numerics) from the pilot corpus; run an automated reachability audit from each fact’s document root; confirm at least 95% have a path of at most six hops using only **structural** edge types (containment, reading order, footnote attachment, cross-reference).

**Acceptance Scenarios**:

1. **Given** a published graph snapshot and a cited evidence chunk identifier, **When** a reachability audit path query runs from the corresponding document root, **Then** the system returns at least one valid path whose every hop uses a **structural** edge type from the catalog (containment, reading order, footnote attachment, cross-reference).
2. **Given** an agent traversal log for a completed query, **When** an auditor reviews cited chunks, **Then** each citation can be mapped to a path from document root to chunk without off-graph hops.
3. **Given** a chunk with no path from its document root within the hop budget, **When** audit runs, **Then** that chunk is flagged as unreachable and MUST NOT be used as grounded evidence until the graph is repaired or the hop budget is revised with recorded approval.

---

### User Story 4 - Pilot Reachability Audit and Transparency (Priority: P4)

Before promoting a snapshot to production retrieval, a steward runs a reachability audit on the pilot corpus and receives a summary: pass rate, failed facts, hop-length distribution, and edge-type coverage. Stakeholders use this to gate releases and track graph quality over time.

**Why this priority**: The stated success metric (95% reachable within N hops) requires a repeatable audit, not ad-hoc inspection.

**Independent Test**: Run the audit against the pilot corpus after materialization; export a machine-readable report showing ≥95% of sampled numeric facts reachable within six hops or listing failures with reasons.

**Acceptance Scenarios**:

1. **Given** a pilot corpus definition and hop budget N=6, **When** the reachability audit runs, **Then** the report states the percentage of audited facts reachable, average hop count, and per-filing breakdown.
2. **Given** audit pass rate below 95%, **When** results are reviewed, **Then** the snapshot is marked not ready for production retrieval until remediation or an explicit waiver with documented rationale.
3. **Given** a successful audit, **When** the snapshot is published, **Then** snapshot metadata references audit version, date, hop budget, and pass rate.

---

### Edge Cases

- What happens when Docling parsing yields sections but no extractable tables? Graph materialization MUST still produce section and paragraph nodes; tables are omitted without failing the whole filing unless table extraction was a mandatory input for that form type.
- How are duplicate footnote identifiers handled? The system MUST not create ambiguous footnote-attachment edges; duplicates are flagged and attached using a documented precedence rule (first resolved target wins; others marked unresolved).
- What happens when cross-references point outside the filing (external exhibits)? Edges MUST NOT fabricate off-corpus targets; unresolved external references are recorded and excluded from traversable paths.
- How are restated or amended filings represented? Temporal-transition edges MUST connect period-ordered documents; amended filings supersede prior accessions for the same fiscal period in temporal metadata without deleting historical document nodes from the snapshot history.
- What happens when semantic similarity produces noisy links? Similarity edges are supplementary; agents MUST prefer structural containment paths for primary citation and MAY use similarity edges only when documented in traversal policy. Such edges MUST NOT satisfy the structural reachability audit (SC-001).
- What happens when a filing contains very large XBRL fact sets? The system MUST materialize **every** parsed fact instance (all contexts/periods) into the graph without an artificial per-filing cap; snapshot sizing and performance are managed operationally, not by silent fact dropping.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST materialize knowledge graphs from XBRL-primary parsed filings without replacing or bypassing the existing parsing contract (structured sections, tables, footnotes, and XBRL fact tables remain the sole parse inputs). Every consolidated XBRL fact instance (each value + period context) MUST be represented as a graph node—no artificial per-filing fact cap.
- **FR-002**: System MUST create typed nodes for document, section, table, row, paragraph, and XBRL fact entities, each carrying stable identifiers, human-readable labels, and provenance back to the source filing (form type, period, accession).
- **FR-003**: System MUST create containment edges linking each child chunk to its parent (document → section → table → row; document → section → paragraph; document → XBRL facts section → fact) so every evidence chunk has an unbroken containment chain to a document root.
- **FR-004**: System MUST create reading-order edges reflecting sequential section and in-section chunk order within a filing.
- **FR-005**: System MUST create footnote-attachment edges when referring and target footnote chunks both exist; unresolved references MUST be recorded and MUST NOT be represented as traversable attachment edges.
- **FR-006**: System MUST create cross-reference edges between in-filing chunks when both endpoints resolve in the same parse.
- **FR-007**: System MUST create temporal-transition edges between document nodes of the same issuer within a multi-filing snapshot, ordered by reporting period with preserved period metadata.
- **FR-008**: System MUST create semantic-similarity edges using a **hybrid** policy: (1) **deterministic** cross-period links when XBRL concept identity and compatible period metadata match across filings; (2) **optional embedding-based** thematic links for narrative risk co-mention only when similarity score exceeds a documented threshold. Each edge MUST carry link method (deterministic | thematic), score metadata when applicable, and period/concept labels sufficient for audit.
- **FR-009**: System MUST publish a documented catalog of allowed node types and edge types consumed by retrieval agents and audit tools; traversal MUST restrict to this catalog.
- **FR-010**: System MUST support path queries from any document node to any evidence chunk in the same filing using only catalog edge types.
- **FR-011**: System MUST fail closed when mandatory structural links for a filing cannot be represented (including document with no sections, orphaned evidence chunks without containment parent, or broken mandatory containment chain); such filings MUST be excluded from the published snapshot with explicit failure reasons.
- **FR-012**: System MUST provide a pilot reachability audit over a **stratified sample of at least 100** numeric facts drawn from **XBRL fact nodes and material table-row numerics** across pilot filings, measuring shortest-path hop count from document root using **structural edge types only** (containment, reading order, footnote attachment, cross-reference), and reporting pass rate against the configured hop budget. Temporal-transition and semantic-similarity edges MUST NOT count toward this audit.
- **FR-013**: System MUST treat reachability audit pass rate ≥ 95% within hop budget N=6 on the pilot corpus as the release gate unless a documented waiver is recorded.
- **FR-014**: Agentic retrieval trajectories MUST record edge types used along citation paths so post-hoc audit can reconstruct document-to-chunk navigation.
- **FR-015**: Graph materialization MUST integrate with existing issuer snapshot versioning so each snapshot version immutably references its graph artifact, node counts, edge counts, and audit summary.
- **FR-016**: Graph materialization MUST use **docling-graph** as the primary mapper producing the catalog node and edge types; the prior custom-only graph builder MUST NOT remain the default publish path after this feature ships.

### Key Entities

- **Graph Node**: A typed vertex (document, section, table, row, paragraph, XBRL fact) with identifier, label, optional numeric or textual payload reference, and filing provenance.
- **Graph Edge**: A typed directed relationship (containment, reading order, footnote attachment, cross-reference, temporal transition, semantic similarity) with source and target node identifiers and type-specific metadata (period, concept, similarity score, unresolved flag).
- **Graph Snapshot**: A versioned issuer-level graph artifact bundling nodes and edges for one or more filings, plus manifest metadata (counts, builder version, audit status).
- **Edge Type Catalog**: The authoritative list of node and edge types and traversal rules exposed to agents and audits.
- **Reachability Audit Report**: Outcome of pilot sampling—per-fact hop count, pass/fail, edge types used on shortest path, and aggregate pass rate against hop budget N.
- **Materialization Job**: Per-filing or per-snapshot run record with success, partial, or failed status and reasons for excluded filings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the pilot corpus, at least **95%** of audited numeric facts have a documented traversal path of **at most six hops** from their document root to the fact or row node, using only **structural** catalog edge types (containment, reading order, footnote attachment, cross-reference).
- **SC-002**: **100%** of filings included in a published snapshot have a complete containment chain from document root to every indexed evidence chunk (zero orphaned chunks in published snapshots).
- **SC-003**: For multi-filing issuer snapshots with four or more periods, **100%** of consecutive reporting periods are connected by temporal-transition edges unless explicitly documented as single-filing mode.
- **SC-004**: Steward can complete a reachability audit report and snapshot publish/no-publish decision in under **10 minutes** of operator time after materialization finishes (excluding compute time).
- **SC-005**: For a sample of **20** agent queries with citations, auditors can reconstruct document-to-chunk paths from trajectory records alone in **≥ 90%** of citations without manual graph inspection.

## Assumptions

- Docling XBRL-primary parsing and existing issuer corpus materialization (multi-filing snapshots) remain upstream dependencies; this feature upgrades graph construction and linkage, not ingestion or parse format.
- **docling-graph** is the **sole** graph materialization engine for v1; the existing custom graph builder is replaced (or thin-wrapped) after reachability parity tests—dual graph artifacts are out of scope.
- Pilot corpus defaults to the same issuer set and filing mix used for multi-filing corpus validation (e.g., one large-cap issuer with latest 10-K and trailing 10-Qs) unless expanded in planning.
- Hop budget **N = 6** is sufficient for document → section → intermediate → chunk paths including XBRL fact sections; planning may revise N after baseline audit.
- Semantic-similarity v1 is **hybrid**: deterministic concept matching is required for cross-period financial facts; embedding-based thematic links are optional and threshold-gated. Similarity edges do not replace structural containment for primary grounding; thematic thresholds are defined during planning.
- Footnote and cross-reference resolution is limited to in-filing targets present in the parse; external exhibits are out of scope for v1 traversable edges.
- Reachability audit uses a **stratified sample of at least 100** facts from **XBRL fact nodes and material table-row numerics** across pilot filings; stratification rules (by form type and filing) are defined during planning. The audit population is drawn from **all** materialized fact nodes because there is no fact-indexing cap.
