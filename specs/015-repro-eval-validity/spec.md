# Feature Specification: Reproduction Evaluation Validity & Stratified Ablations

**Feature Branch**: `015-repro-eval-validity`

**Created**: 2026-06-06

**Status**: Draft

**Input**: Harden paper-v1.0 reproduction evaluation after discovering inverted outcome_accuracy (ablation-no-walker and ablation-xbrl-only beating graph-full due to judge artifacts), 500+ noisy per-item report warnings, and ablation variants that abstain on HTML-labeled items. P0 is already merged on main (deferred-judge trajectory hydration from serialized snapshots, abstention penalty when answer/rubric ground truth exists, GT-aware judge criteria value_alignment and claim_presence, export-tables loading item context from custom-judge bundle). This feature delivers the remaining work in three phases: P1 evaluation validity and graph agent quality, P2 report investigation UX, P3 stratified ablation reporting. Depends on features 011, 012, 013, 014. Out of scope: re-running full 1000-query agent reproduction, new ablation variant definitions, changing walker or xbrl_only retrieval behavior.

## Clarifications

### Session 2026-06-06

- Q: How should `primary_evidence_source` be assigned when an item has multiple labeled chunks of different types? → A: Uniform stratum rule — all HTML narrative chunk ids → `html`; all XBRL chunk ids → `xbrl`; both types present → `mixed`; empty labels → `unknown`.
- Q: What is the re-judge scope for existing paper-v1.0 checkpoints? → A: Full re-judge across all variants with idempotent resume — skip items already scored at judge version ≥ v2 with non-empty trajectory evidence.
- Q: What acceptance threshold applies for graph-full vs abstaining ablations on outcome_accuracy (SC-001)? → A: Strict ordering — graph-full MUST be strictly greater than both abstaining ablations on the full dev split (no tolerance band).
- Q: How should stratum-scoped variant deltas be exported (FR-014)? → A: New file `variant_delta_by_source.csv` with stratum column; existing `variant_delta.csv` remains pooled full-split deltas only.
- Q: Which variants receive structural audit metrics (FR-005)? → A: All five standard variants — accession binding, section path hit rate, and multi-filing success recorded per variant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy Headline Scores After Re-Judge (Priority: P1)

A researcher who already completed a full paper reproduction run wants to re-score existing per-item results without re-running agents, then export headline tables where outcome accuracy aligns with ranking metrics and no longer rewards abstention when the benchmark expects a substantive answer.

**Why this priority**: Paper headline numbers are blocked until outcome metrics are trustworthy; foundational scoring fixes exist on main but operators need a verified workflow and acceptance criteria before citing cross-variant outcome comparisons.

**Independent Test**: Re-score an existing `paper-v1.0` output directory (full dev split, all variants; resume skips v2+ items with hydrated evidence), re-export tables, and confirm graph-full outcome accuracy exceeds abstaining ablation variants while ranking metrics still favor graph-full over flat-chunk.

**Acceptance Scenarios**:

1. **Given** a completed reproduction output with per-variant item results and a documented re-judge workflow, **When** the operator re-scores and re-exports headline tables, **Then** graph-full outcome accuracy is strictly greater than both ablation-no-walker and ablation-xbrl-only on the full dev split.
2. **Given** a benchmark item with answer ground truth and an abstention response (no substantive answer, no citations), **When** headline outcome is computed, **Then** that item contributes zero to outcome accuracy.
3. **Given** a benchmark item with answer ground truth and a substantive cited answer, **When** headline outcome is computed, **Then** the score reflects answer correctness (not merely absence of unsupported claims).
4. **Given** a benchmark item with rubric ground truth only, **When** rubric alignment is computed, **Then** abstention yields zero alignment contribution.

---

### User Story 2 - Graph Agent Quality and Structural Audit (Priority: P1)

An evaluation engineer wants graph-full runs to produce financially grounded answers and complete structural audit metrics recorded alongside each variant run, so paper claims about navigation and binding can be supported.

**Why this priority**: Ranking metrics show graph retrieval works; remaining gaps are synthesis quality on partial evidence and missing structural binding scores in reproduction run metadata.

**Independent Test**: Run a smoke reproduction on graph-full (≥10 items with expected bindings); verify structural audit fields are populated and sampled financebench items do not state numbers unsupported by citations.

**Acceptance Scenarios**:

1. **Given** benchmark items with expected filing bindings, **When** any standard variant completes, **Then** accession binding accuracy is recorded for that variant in reproduction run metadata (not left as zero placeholders).
2. **Given** items with expected section paths, **When** any standard variant completes, **Then** section path hit rate is recorded for that variant.
3. **Given** multi-filing items, **When** any standard variant completes, **Then** multi-filing success rate is recorded for that variant.
4. **Given** partial evidence for a numeric question, **When** the agent answers, **Then** the response explicitly states what cannot be computed rather than inventing missing values.
5. **Given** an item with non-empty answer citations, **When** results are stored for later judging, **Then** trajectory evidence in stored artifacts is consistent with those citations.

---

### User Story 3 - Readable Investigation Notes (Priority: P2)

A researcher opening the reproduction HTML report after a full run wants concise investigation notes that summarize patterns by variant instead of hundreds of repeated per-item warnings, while still surfacing unexpected graph-full issues.

**Why this priority**: Feature 014 reports are correct but unusable at full scale; operators miss real anomalies in noise.

**Independent Test**: Generate a report from a full five-variant reproduction; investigation section has a bounded number of aggregated notes with counts; expected ablation abstention appears once per pattern.

**Acceptance Scenarios**:

1. **Given** a full reproduction report, **When** investigation notes render, **Then** warnings are grouped by variant and pattern with item counts (e.g., “200 items: judge ok, zero citations”).
2. **Given** expected ablation behavior (no-walker or xbrl-only with zero citations on narrative-labeled items), **When** notes are generated, **Then** a single informational summary explains the pattern instead of one note per item.
3. **Given** a comparison variant with high outcome but zero retrieval overlap and zero citations, **When** “exceeds graph-full” notes are considered, **Then** no warning is raised.
4. **Given** an aggregated note, **When** the operator expands it, **Then** up to five example item identifiers are shown with navigation to item drill-down.

---

### User Story 4 - Stratified Ablation Tables (Priority: P3)

A paper author wants ablation comparisons split by evidence type (HTML narrative, XBRL numeric, mixed) so completed ablation runs remain scientifically useful: HTML stratum shows graph walker value; XBRL stratum shows xbrl-only adequacy; abstention rate is reported as a first-class metric.

**Why this priority**: Pooled headline tables mislead when ablations cannot reach HTML-labeled chunks; stratification extracts value from existing runs without re-running agents.

**Independent Test**: Assign strata on custom-judge dev items, export stratified tables and regenerate report; HTML stratum shows high abstention for no-walker and ranking advantage for graph-full; XBRL stratum shows non-trivial activity for xbrl-only.

**Acceptance Scenarios**:

1. **Given** benchmark items with relevance labels, **When** strata are assigned, **Then** each item receives primary evidence source using the uniform rule: all labeled chunks are HTML narrative → `html`; all are XBRL → `xbrl`; both types present → `mixed`; no labels → `unknown`.
2. **Given** a completed five-variant reproduction, **When** tables are exported, **Then** a by-evidence-source table includes per-variant, per-stratum headline metrics plus abstention rate.
3. **Given** stratified tables, **When** variant deltas are exported, **Then** `variant_delta_by_source.csv` contains stratum-scoped deltas (e.g., graph-full vs no-walker on HTML only) while `variant_delta.csv` remains pooled full-split deltas.
4. **Given** the reproduction report, **When** stratified section renders, **Then** operators see variant-by-metric matrices per stratum with item counts and abstention rate.
5. **Given** the paper-v1.0 release manifest, **When** an author reads ablation guidance, **Then** which cross-variant comparisons are valid per stratum is documented (e.g., no-walker vs graph-full on HTML; xbrl-only vs graph-full on XBRL).

---

### Edge Cases

- Re-judge on partial runs: pending judge items follow existing 013 exclusion rules; export may require explicit allow-pending flag.
- Items with empty relevance labels: assigned unknown stratum and excluded from stratified aggregates with audit count.
- Finder rubric-only items (no answer ground truth): outcome row omitted or marked rubric-only per 012; stratum still assigned; alignment uses rubric criteria.
- Small strata (fewer than 10 items): shown with low-n warning; no paper delta claims auto-generated.
- Old checkpoints missing trajectory evidence but retaining answer citations: re-score still produces valid judge input via citation fallback; such items are not skipped by the v2 resume gate until re-scored.
- Re-judge resume: items at judge version ≥ v2 with non-empty trajectory evidence are skipped; partial variant progress resumes without duplicating API calls.

## Requirements *(mandatory)*

### Functional Requirements

#### Completed dependency (verify, do not re-implement)

- **FR-000**: Reproduction scoring MUST hydrate trajectory evidence from stored snapshots before deferred judging, penalize abstention when ground truth expects an answer, score answer and rubric ground truth via distinct judge criteria, and load item context when re-exporting tables from checkpoints.

#### P1 — Evaluation validity and graph agent quality

- **FR-001**: The kit MUST document a workflow to re-score existing per-variant item results and re-export paper tables without re-running agent queries. Re-judge MUST process all variants on the full dev split; MAY skip items already scored at judge version ≥ v2 with non-empty trajectory evidence (idempotent resume).
- **FR-002**: Headline outcome accuracy MUST assign zero contribution for abstention answers when answer ground truth exists.
- **FR-003**: Headline rubric alignment MUST assign zero contribution for abstention when rubric ground truth exists.
- **FR-004**: Headline outcome accuracy for answer-ground-truth items MUST reflect answer correctness, not abstention-safe synthesis scores alone.
- **FR-005**: Reproduction run metadata MUST record accession binding accuracy, section path hit rate, and multi-filing success rate for **all five standard variants** (non-placeholder values when applicable items exist for that variant).
- **FR-006**: Agent answers MUST not state numeric values absent from cited evidence when evidence is partial; partial cases MUST use explicit cannot-compute wording.
- **FR-007**: Stored trajectory artifacts MUST remain consistent with answer citations for judged items.

#### P2 — Report investigation UX

- **FR-008**: The results viewer MUST aggregate investigation notes by variant and pattern with item counts.
- **FR-009**: Expected ablation abstention patterns (no-walker, xbrl-only zero citations on narrative items) MUST appear as single informational summaries.
- **FR-010**: “Outcome exceeds graph-full” warnings MUST require the comparison variant to show retrieval overlap or non-zero citations.
- **FR-011**: Aggregated notes MAY expose up to five example item identifiers linked to drill-down.

#### P3 — Stratified ablation reporting

- **FR-012**: Each custom-judge dev item MUST receive primary evidence source at publish or export time using the uniform stratum rule: if every `relevant_chunk_id` is an HTML narrative chunk → `html`; if every id is XBRL → `xbrl`; if both types appear → `mixed`; if labels are empty → `unknown`.
- **FR-013**: Paper export MUST include a by-evidence-source table with headline metrics and abstention rate per variant and stratum.
- **FR-014**: Paper export MUST produce `variant_delta_by_source.csv` with columns including `primary_evidence_source`, `baseline_variant`, `comparison_variant`, `metric_name`, and `delta`. Existing `variant_delta.csv` MUST remain pooled full-split deltas only (unchanged schema).
- **FR-015**: The results viewer MUST render a stratified ablation section per evidence source.
- **FR-016**: The paper-v1.0 release manifest MUST document valid ablation comparisons per stratum.
- **FR-017**: Ablation variants MUST continue to execute on the full dev split; stratification is a reporting partition only.

### Key Entities

- **EvidenceStratum**: Per-item classification (html, xbrl, mixed, unknown) derived from relevance labels via the uniform all-or-mixed rule (not majority vote or profile heuristics).
- **AbstentionRate**: Per variant and stratum, fraction of items where the agent abstained among headline-eligible items.
- **StructuralAuditMetrics**: Per-variant accession binding accuracy, section path hit rate, multi-filing success rate.
- **AggregatedInvestigationNote**: Severity, variant, pattern description, item count, optional example item ids, guidance hint.
- **StratumTableRow**: Variant, stratum, metric name, value, item count, abstention rate, exclusion audit fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After re-scoring an existing paper-v1.0 output, graph-full outcome accuracy is strictly greater than both abstaining ablation variants on the full dev split (no tolerance band applied to cross-variant ordering).
- **SC-002**: At least 80% of graph-full items with citations have non-empty evidence available at re-score time.
- **SC-003**: On a smoke run with binding-heavy items, structural audit metrics are non-zero in reproduction run metadata for each variant that processes those items (all five variants on full repro).
- **SC-004**: Full reproduction reports contain no more than 25 top-level investigation notes (aggregated, not per-item duplicates).
- **SC-005**: Stratified export covers all five standard variants across html, xbrl, and mixed strata with item counts summing to eligible dev items.
- **SC-006**: On the HTML stratum, no-walker abstention rate is at least 80% and graph-full retrieval ranking exceeds no-walker by a documented margin.
- **SC-007**: Operators can re-score, re-export, and regenerate a report from existing output in under 30 minutes of active time (excluding external judge queue time).

## Assumptions

- P0 scoring fixes are merged on main before P1–P3 implementation begins.
- Custom-judge v1.0.0 dev split (200 items) remains the paper headline population; strata partition this set.
- Evidence stratum uses the uniform rule (all HTML → html, all XBRL → xbrl, both → mixed, empty → unknown); no per-item manual tags required for v1.
- External judge configuration and rubrics remain as pinned in the paper-v1.0 manifest.
- Feature 012 exclusion rules for incomplete, degraded, and pending items apply to stratified tables.
- Minimum stratum size for automated delta claims defaults to 10 items.

## Dependencies

- **011** Custom-judge dataset (items, relevance labels, profiles).
- **012** Research reproduction kit (variants, export schema, headline metrics).
- **013** Benchmark eval acceleration (deferred judge, checkpoints).
- **014** Repro results viewer (report rendering, anomaly hooks).

## Out of Scope

- Re-running the full five-variant agent reproduction (1000 queries) unless the operator chooses to.
- Defining new ablation variants beyond the five standard variants.
- Changing graph walker or xbrl-only retrieval behavior.
- Automated LaTeX manuscript editing beyond exported tables.
