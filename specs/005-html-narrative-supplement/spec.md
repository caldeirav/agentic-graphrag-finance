# Feature Specification: Supplementary SEC HTML Narrative Ingestion

**Feature Branch**: `005-html-narrative-supplement`

**Created**: 2026-05-21

**Status**: Draft

**Input**: User description: "Add supplementary ingestion of SEC filing HTML narrative (MD&A, risk factors, business description) for the same accession as an already-cached XBRL package, without replacing XBRL as the primary source for numeric facts. Parsed narrative sections must merge into the same issuer graph snapshot with clear source tagging (XBRL vs HTML) so retrieval can prefer XBRL for numbers and HTML for qualitative claims. Users must see citations that identify which source type supported each sentence. Out of scope: replacing XBRL parsing or ingesting HTML without a matching XBRL package for the same filing. Success: qualitative benchmark items that require MD&A prose retrieve at least one HTML-sourced chunk when XBRL facts alone are insufficient."

## Clarifications

### Session 2026-05-21

- Q: Which HTML artifact is the supplementary narrative source? → A: **Prefer narrative extraction from the cached inline/iXBRL HTML already in the XBRL package**; fetch a separate filing `.htm` from EDGAR only when that document is missing or unsuitable for section extraction.
- Q: How should retrieval choose XBRL vs HTML evidence? → A: **LLM router** classifies each query intent (numeric, qualitative, hybrid) before evidence extraction; micro-extractor and ranking apply source bias from that classification.
- Q: Where should XBRL and HTML parses merge? → A: **Single merged `ParsedDocument` per accession** with per-section (and chunk) source tags (`XBRL` | `HTML`); one serialized parse artifact per accession under `data/parsed/`.
- Q: When should HTML narrative run in `materialize`? → A: **On by default** when a complete XBRL package exists; operators may opt out via flag (e.g. `--skip-html-narrative`) for XBRL-only fast materialize.
- Q: What if the LLM intent router fails or is unavailable? → A: **Deterministic keyword fallback** classifies numeric / qualitative / hybrid when the router errors or returns an invalid label; trajectory records `intent_source=keyword_fallback`.
- Q: Should router intent and fallback be observable in agent tracing? → A: **Yes** — every ask MUST persist router intent, intent source (LLM vs keyword fallback), applied source bias, and fallback reason (when applicable) in the durable trajectory store and run-level observability artifacts for audit and benchmarks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Supplementary HTML Fetch for Cached XBRL Filings (Priority: P1)

A pipeline operator or analyst has already ingested the full XBRL package for a filing accession. The system uses the **inline/iXBRL HTML document already present in that package** as the primary narrative source (MD&A, risk factors, business description). A separate filing `.htm` is downloaded from EDGAR only when the inline document is missing or unsuitable; either path links to the existing XBRL cache entry and records narrative ingestion as supplementary—not a replacement for structured XBRL artifacts.

**Why this priority**: Without paired HTML alongside XBRL, downstream parsing and graph merge have nothing qualitative to index; this is the ingestion gate for the feature.

**Independent Test**: Given a cached XBRL-complete accession, run supplementary HTML ingest; verify HTML artifact exists under the accession directory, manifest records both XBRL and HTML roles, and ingest refuses to run when no matching XBRL package exists.

**Acceptance Scenarios**:

1. **Given** a valid cached XBRL package for an accession, **When** supplementary HTML ingestion runs, **Then** HTML narrative artifacts are stored alongside XBRL under the same accession path and manifest lists both source types.
2. **Given** an accession with no cached XBRL package, **When** supplementary HTML ingestion is requested, **Then** the system rejects the operation with an explicit error and does not create orphan HTML-only cache entries.
3. **Given** HTML download fails for an otherwise valid accession, **When** ingestion completes, **Then** per-filing status records failure without invalidating the existing XBRL cache.
4. **Given** a multi-filing corpus materialize job without opt-out, **When** each member has XBRL cached, **Then** supplementary HTML narrative extract-and-merge runs per included member without re-downloading XBRL unless refresh is requested.
5. **Given** `materialize` with HTML narrative opt-out enabled, **When** the job completes, **Then** only XBRL-primary parse paths run and manifest records HTML as skipped (not failed).
6. **Given** a cached XBRL package whose inline/iXBRL HTML is missing or unsuitable, **When** supplementary narrative ingestion runs, **Then** the system attempts fallback download of the primary filing `.htm` and records which artifact path was used on the manifest.

---

### User Story 2 - Parse and Tag Narrative Sections (Priority: P2)

The system parses HTML narrative into structured sections (at minimum MD&A, risk factors, and business description where present), tags each section with source type **HTML**, and **merges into the existing per-accession `ParsedDocument`** so one serialized parse artifact contains both XBRL-primary structure (tables, facts) and HTML narrative sections—without overwriting XBRL-derived fields.

**Why this priority**: Retrieval and graph merge need labeled narrative chunks; parsing is the bridge between raw HTML and the knowledge graph.

**Independent Test**: Parse HTML for one 10-K fixture with cached XBRL; verify output includes labeled sections for MD&A (or equivalent), risk factors, and business description when present in the filing, each marked as HTML-sourced.

**Acceptance Scenarios**:

1. **Given** cached HTML for a 10-K accession, **When** narrative parsing runs, **Then** parsed sections include human-readable titles and body text tagged with source type HTML.
2. **Given** the same accession already has an XBRL-primary parsed document, **When** narrative parse completes, **Then** the merged `ParsedDocument` persisted to disk contains both XBRL-tagged and HTML-tagged sections in one file, with numeric tables and facts remaining XBRL-attributed.
3. **Given** a filing where a target section is absent (e.g., no separate risk factors heading), **When** parsing completes, **Then** the system records absent sections without failing the entire filing when other narrative sections succeed.
4. **Given** malformed or empty HTML body, **When** parsing is attempted, **Then** the filing records parse failure for HTML narrative while XBRL parse remains usable.

---

### User Story 3 - Unified Graph with Source-Aware Evidence (Priority: P3)

Materialization merges HTML narrative sections into the **same** issuer graph snapshot as XBRL facts and tables, with every evidence node carrying a source-type tag (XBRL or HTML). Before evidence extraction, an **LLM router** classifies each query intent (numeric, qualitative, or hybrid). Retrieval then biases toward XBRL-sourced chunks for numeric intent, HTML-sourced chunks for qualitative intent (MD&A, risk language, business description), and blended ranking for hybrid—without mixing sources silently in citations.

**Why this priority**: This delivers the user-visible value—grounded answers that use the right artifact class per claim type.

**Independent Test**: Materialize a snapshot for an issuer with both XBRL and HTML parsed; verify graph nodes include HTML-tagged paragraph/section nodes under the same document accession as XBRL facts, and reachability from document root holds for sampled HTML chunks.

**Acceptance Scenarios**:

1. **Given** combined XBRL and HTML parse for one accession, **When** graph materialization runs, **Then** one document node per accession contains both XBRL and HTML child chunks with distinct source-type metadata on each node.
2. **Given** a revenue numeric query, **When** the LLM router classifies intent as numeric and retrieval runs, **Then** ranked evidence prioritizes XBRL fact nodes over HTML narrative unless XBRL evidence is insufficient.
3. **Given** a qualitative MD&A or risk-factor query, **When** the router classifies intent as qualitative and XBRL alone cannot answer, **Then** at least one HTML-sourced narrative chunk is included in evidence.
4. **Given** a hybrid query (e.g., revenue trend with management explanation), **When** the router classifies intent as hybrid, **Then** evidence includes both XBRL and HTML chunks with source types preserved.
5. **Given** a published snapshot, **When** structural reachability audit runs, **Then** HTML narrative chunks are included in the audit population where they contain material prose (configurable stratification).

---

### User Story 4 - Source-Tagged Citations in Answers (Priority: P4)

When the agent answers a question, each cited evidence item and the rendered answer identify whether support came from **XBRL** or **HTML** narrative, so analysts can audit provenance at sentence level.

**Why this priority**: Constitution and user trust require traceability; mixed-source answers without labeling violate the stated success condition.

**Independent Test**: Run `ask` on a qualitative benchmark item requiring MD&A prose; verify answer citations include source type and trajectory records the same.

**Acceptance Scenarios**:

1. **Given** an answer citing both an XBRL fact and an HTML paragraph, **When** the user views citations, **Then** each citation displays source type XBRL or HTML and accession/section identity.
2. **Given** an answer supported only by HTML narrative, **When** citations render, **Then** all citations are labeled HTML and no citation falsely claims XBRL numeric grounding.
3. **Given** a completed query logged to the trajectory store, **When** an auditor reviews the run, **Then** evidence records include source type alongside excerpt and graph node identifier.

---

### User Story 5 - Router Observability in Agent Tracing (Priority: P4)

An engineer or benchmark auditor needs to see **why** retrieval preferred XBRL or HTML for a given ask: the router’s intent label, whether the LLM or keyword fallback produced it, and what source bias was applied—without re-running the query or reading application logs.

**Why this priority**: Source-aware retrieval is policy-driven; without router tracing, debugging wrong citations (e.g., numeric answer from HTML prose) is guesswork and violates constitution traceability expectations.

**Independent Test**: Run `ask` with a qualitative query; open the persisted trajectory / run artifacts and verify `query_intent`, `intent_source`, and `source_bias` are present; repeat with router forced to fail and verify fallback fields are populated.

**Acceptance Scenarios**:

1. **Given** a successful ask where the LLM router classifies intent, **When** the trajectory is persisted, **Then** it includes `query_intent` (numeric | qualitative | hybrid), `intent_source=llm`, and `source_bias_applied` (xbrl_primary | html_primary | blended).
2. **Given** a successful ask where keyword fallback runs, **When** the trajectory is persisted, **Then** it includes `intent_source=keyword_fallback`, the resolved `query_intent`, and a non-empty `router_fallback_reason` (e.g., timeout, invalid_label, mock_mode).
3. **Given** any ask run, **When** an auditor inspects run-level observability output, **Then** router fields are available as structured data (not only embedded in free-text LLM rationale) and correlate with the same `snapshot_id` and query text as the answer.
4. **Given** a benchmark replay of N qualitative items, **When** aggregation runs over trajectories, **Then** at least **95%** of runs expose all required router fields for automated pass/fail checks.

---


### Edge Cases

- What happens when HTML is available but section boundaries cannot be detected? System MUST still persist best-effort narrative blocks with a generic section label and HTML source tag; it MUST NOT drop XBRL materialization for that filing.
- What happens when HTML and XBRL section titles overlap? Merge MUST keep separate provenance; duplicate text MUST NOT collapse into a single untagged node.
- What happens when only abbreviated 10-Q HTML is available? Parser MUST extract available narrative portions; missing long-form sections are recorded as absent, not invented.
- What happens when user forces refresh on HTML only? Refresh MUST not delete or replace XBRL instance artifacts without an explicit full refresh policy.
- What happens when qualitative benchmark expects MD&A but filing has minimal prose? Benchmark item MAY fail with insufficient evidence; system MUST NOT hallucinate HTML content.
- What happens when the LLM intent router is unavailable (mock LLM, timeout)? System MUST apply keyword fallback intent classification and continue ask with trajectory annotation—MUST NOT fail solely because the router failed.
- What happens when router and macro-router both emit routing metadata? Intent router trace MUST be the canonical record for numeric/qualitative/hybrid intent; other stages MUST NOT overwrite `query_intent` on the trajectory.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest supplementary SEC filing HTML narrative only for accessions that already have a complete cached XBRL package; HTML-only ingestion for an accession is prohibited. Narrative extraction MUST **prefer the inline/iXBRL HTML document already in the cached XBRL package**; a separate filing `.htm` download is permitted only as fallback when the inline document is missing or unsuitable.
- **FR-002**: System MUST preserve XBRL as the **primary** source for numeric facts, financial statement tables, and taxonomy-backed metrics; HTML MUST NOT replace or supersede XBRL parsing for those purposes.
- **FR-003**: System MUST parse HTML narrative into structured sections covering, at minimum, MD&A, risk factors, and business description when those sections exist in the filing HTML.
- **FR-003b**: System MUST merge HTML narrative sections into the **same** per-accession `ParsedDocument` (single `data/parsed/{ticker}/{accession}.json` artifact) with explicit per-section `source_type` metadata (`XBRL` | `HTML`); sidecar-only HTML parse files without merging into `ParsedDocument` are not permitted for v1.
- **FR-004**: System MUST tag every narrative-derived section and graph node with source type **HTML**; every XBRL-derived section and node MUST retain source type **XBRL** (or equivalent unambiguous labels documented in the product glossary).
- **FR-005**: System MUST merge HTML narrative sections into the same issuer-level graph snapshot and document hierarchy as existing XBRL materialization for that accession (one document node per accession with typed child chunks).
- **FR-006**: An **LLM router** MUST classify each query into intent **numeric**, **qualitative**, or **hybrid** before micro-extraction; retrieval MUST apply source bias from that classification (XBRL for numeric, HTML for qualitative, blended for hybrid). When the router fails or returns an invalid label, a **deterministic keyword fallback** MUST classify intent and the trajectory MUST record `intent_source=keyword_fallback`.
- **FR-007**: When XBRL evidence alone is insufficient for a qualitative or hybrid question, retrieval MUST attempt HTML narrative chunks before returning insufficient evidence; router intent, intent source (LLM vs fallback), and source bias MUST be recorded in the trajectory.
- **FR-008**: Answer presentation and trajectory records MUST expose source type (XBRL vs HTML) for each citation supporting the answer text.
- **FR-009**: System MUST NOT alter ingestion or parsing contracts for XBRL packages except to add optional supplementary HTML steps and merged parse/graph outputs.
- **FR-010**: Corpus materialize and ask workflows MUST continue to operate on issuer snapshots; supplementary HTML MUST integrate into existing materialize → parse → graph → ask paths without a parallel snapshot format. HTML narrative extract-and-merge MUST run **by default** on `materialize` when XBRL is complete; an documented opt-out flag MUST allow XBRL-only materialize for operators.
- **FR-011**: Per-filing status MUST distinguish XBRL success, HTML success, HTML skipped (no package), and HTML failed independently.
- **FR-012**: Evaluation benchmarks that require MD&A or risk prose MUST be able to assert presence of at least one HTML-sourced citation when XBRL-only evidence cannot satisfy the item.
- **FR-013**: Every production `ask` MUST emit an **intent router trace** on the durable agent trajectory before micro-extraction completes, including at minimum: `query_intent`, `intent_source` (`llm` | `keyword_fallback`), `source_bias_applied`, and `router_model_id` or equivalent run identifier when LLM was used.
- **FR-014**: When keyword fallback is used, the trajectory MUST include `router_fallback_reason` (e.g., `llm_timeout`, `invalid_label`, `mock_llm`, `router_error`) and MUST NOT mislabel `intent_source` as `llm`.
- **FR-015**: Run-level observability MUST expose router trace fields as structured run parameters or a dedicated artifact (e.g., intent router summary JSON) linked to the same MLflow run / trajectory URI as the answer, so benchmarks and operators can audit without re-invoking the LLM.
- **FR-016**: Micro-extraction and synthesis stages MUST read `query_intent` and `source_bias_applied` from trajectory state; evidence ranking changes MUST be attributable to the recorded router decision in post-hoc review.

### Key Entities

- **Supplementary HTML Artifact**: Narrative HTML source for an accession—primarily the **inline/iXBRL HTML** already in the XBRL package; optionally a separately downloaded filing `.htm` recorded in the manifest with role distinct from taxonomy instance artifacts when used as fallback.
- **Narrative Section**: Parsed block (MD&A, risk factors, business description, or fallback) with title, body text, and source type HTML.
- **Combined Parsed Filing**: Single per-accession `ParsedDocument` unifying XBRL-primary structure and HTML narrative sections with per-section `source_type` tags, serialized as one JSON artifact.
- **Source Type**: Enumeration exposed to graph, retrieval, and citations (XBRL | HTML).
- **Source-Tagged Citation**: Citation record binding excerpt, graph node, accession, and source type for audit display and trajectories.
- **Query Intent Classification**: Router output (numeric | qualitative | hybrid) driving source-biased evidence ranking for each ask.
- **Intent Router Trace**: Per-ask routing record with `query_intent`, `intent_source`, `source_bias_applied`, optional `router_fallback_reason`, and timestamp ordering relative to evidence extraction.

### Observability Fields *(router trace contract)*

| Field | Values | Required when |
|-------|--------|----------------|
| `query_intent` | `numeric`, `qualitative`, `hybrid` | Always |
| `intent_source` | `llm`, `keyword_fallback` | Always |
| `source_bias_applied` | `xbrl_primary`, `html_primary`, `blended` | Always |
| `router_fallback_reason` | `llm_timeout`, `invalid_label`, `mock_llm`, `router_error`, … | `intent_source=keyword_fallback` |
| `router_latency_ms` | non-negative integer | Optional v1 |
| `router_raw_label` | string | Optional v1 (LLM path only) |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a pilot set of qualitative benchmark items that require MD&A or risk-factor prose, at least **90%** of items retrieve **at least one** HTML-sourced evidence chunk when XBRL facts alone are insufficient to answer.
- **SC-002**: For a pilot set of numeric benchmark items (revenue, assets, EPS), at least **95%** of answers use XBRL-sourced citations as the primary numeric support (HTML may supplement narrative context but not replace XBRL numbers).
- **SC-003**: **100%** of successful ask responses that include citations display source type (XBRL or HTML) on every citation in CLI and JSON output modes.
- **SC-004**: Supplementary HTML ingestion completes for cached XBRL accessions without invalidating existing XBRL manifests in **100%** of successful paired ingest runs on the pilot corpus.
- **SC-005**: Combined materialized snapshots include both XBRL fact nodes and HTML narrative nodes for at least **80%** of pilot 10-K accessions where HTML download succeeds.
- **SC-006**: **100%** of successful `ask` runs in a pilot audit set persist a complete intent router trace (`query_intent`, `intent_source`, `source_bias_applied`); **100%** of fallback runs additionally include `router_fallback_reason`.
- **SC-007**: For a sample of **20** benchmark replays, external reviewers can determine the router intent and whether fallback occurred using trajectory / run artifacts alone in **≥ 95%** of cases without re-running the query.

## Assumptions

- Most cached XBRL packages already include an inline/iXBRL HTML document suitable for narrative section extraction; separate filing `.htm` fetch is a fallback, not the default path.
- When neither inline nor fallback HTML is available or parseable, HTML narrative ingest fails gracefully per filing without invalidating XBRL.
- Existing XBRL-primary Docling (or equivalent) parse pipeline remains authoritative for structured facts; HTML parsing may use HTML-specific extraction (section headings, item boundaries) without re-running full XBRL taxonomy parse on HTML.
- Section detection uses filing-specific headings (e.g., Item 1, Item 1A, Item 7) with reasonable defaults for large-cap issuers; perfect boundary detection for all filers is not required in v1 but absent sections must be reported.
- Graph materialization extends the current issuer snapshot model (003/004); no second graph per issuer.
- Qualitative benchmark subset is defined during planning (e.g., FinAgentBench or project benchmark items tagged `requires_narrative`).
- Users operate through existing `agent-query materialize` and `agent-query ask` commands; no separate HTML-only CLI is required for v1. Default materialize includes HTML narrative; opt-out is for speed or CI fixtures that only need XBRL.
- Query intent classification uses the same local LLM stack as other agent routing steps unless planning specifies otherwise.
- Agent trajectories are persisted to the project’s standard observability store (MLflow per constitution); router trace fields integrate into existing `trajectory.json` (or equivalent) rather than introducing a separate user-facing audit UI in v1.

## Out of Scope

- Replacing XBRL parsing or making HTML the primary structured source for financial statements.
- Ingesting HTML for accessions without a matching cached XBRL package.
- Scraping external exhibits or third-party sites not part of the official filing HTML for that accession.
- Real-time streaming ingestion or push notifications on new filings.
- Automatic translation or summarization of narrative; only retrieval and citation of source prose.
