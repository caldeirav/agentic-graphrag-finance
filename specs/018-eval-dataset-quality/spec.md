# Feature Specification: Evaluation Dataset Quality Improvement and Management

**Feature Branch**: `018-eval-dataset-quality`

**Created**: 2026-06-20

**Status**: Draft

**Input**: Build an evaluation dataset quality improvement and management workflow for custom-judge bundles (starting from v2.0.0 / paper-v1.0).

## Clarifications

### Session 2026-06-20

- Q: For the v2.0.0 → quality-pass bundle, how should items be improved? → A: **In-place patch** — fix the existing 200 dev items via overrides and per-slot regeneration; preserve item identities where possible; publish as v2.0.1 extend from parent.
- Q: Where should review annotations be stored? → A: **Draft sidecar** — append-only `annotations.jsonl` inside the draft bundle directory; overrides merge into dev items only on explicit apply.
- Q: What threshold ranks an item highest in the reproduction-driven review queue? → A: **Moderate retrieval** — MRR ≥ 0.5 or nDCG@10 ≥ 0.3 with outcome score = 0.
- Q: When v2.0.1 is published after the quality pass, how should paper reproduction reference it? → A: **New paper release** — publish `paper-v1.1` manifest pointing at v2.0.1 with new expected checksums; paper-v1.0 remains immutable.
- Q: What format should the exported review pack use? → A: **HTML + CSV** — static HTML for human review; companion CSV with the same rows for annotation import and queue filtering. Operators must review benchmark items structurally (bindings, section paths, ground truth, required claims) and outcome-driven (low outcome scores or ranking anomalies from reproduction results), with per-item annotations and two improvement paths: (1) corrective loop—aggregate failure patterns into generation-spec feedback and targeted item regeneration; (2) human-in-the-loop—apply approved per-record overrides to draft bundles with audit trail before publish. Address known v2.0.0 quality defects: weak generation diversity (~40% duplicate rejections), templated comparison canonical answers, and high zero-outcome-score rate partly attributable to dataset quality. Integrate with existing generate, publish, extend, pool selection, feasibility/scorability gates, and reproduction item drill-down. Published bundle artifacts remain the source of truth for evaluation locks. Out of scope: changing ranking metric definitions; new model endpoints; retroactive paper-v1.0 score updates without a new bundle version.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproduction-Driven Review Queue (Priority: P1)

A dataset operator exports a prioritized review queue from a completed paper reproduction, separating items where retrieval succeeded but outcome scored zero (likely ground-truth or judge-alignment issues) from items where retrieval failed (likely agent or binding issues).

**Why this priority**: Roughly half of v2.0.0 dev items score zero on the best system variant; without triage, reviewers waste time on agent failures and miss fixable dataset defects that depress headline outcome metrics.

**Independent Test**: Given reproduction results for the baseline variant and the published dev split, export a review queue; verify high-retrieval/zero-outcome items rank above low-retrieval items and each row includes question, bindings, ground truth, claims, and reproduction scores.

**Acceptance Scenarios**:

1. **Given** a completed reproduction on the v2.0.0 dev split, **When** the operator exports a review queue, **Then** items with MRR ≥ 0.5 or nDCG@10 ≥ 0.3 and outcome score = 0 rank above items with weaker retrieval metrics.
2. **Given** a queued item, **When** the operator opens its review pack, **Then** they see structural fields (bindings, section paths, answer, required claims) and outcome/ranking scores from reproduction without re-running agents.
3. **Given** an item annotated as agent failure, **When** the queue is filtered, **Then** that item can be excluded from the dataset-quality worklist without blocking publish of unrelated fixes.

---

### User Story 2 - Per-Item Annotation and Corpus Spot-Check (Priority: P1)

A reviewer annotates individual benchmark items with a failure classification, notes, and optional proposed corrections, verifying each answer and required claim against the bound filing sections in the bundled corpus before approving a change.

**Why this priority**: v2.0.0 publish required only a 20-item stratified audit; systematic per-item review with corpus verification is needed to catch factually weak or misaligned ground truth.

**Independent Test**: Annotate 5 items from the review queue including at least one comparison item; verify each annotation records reviewer identity, timestamp, failure class, and corpus spot-check status.

**Acceptance Scenarios**:

1. **Given** a review-queue item, **When** the reviewer records an annotation, **Then** they MUST assign one failure class from: `gt_too_strict`, `gt_wrong`, `gt_boilerplate`, `question_ambiguous`, `claims_misaligned`, `acceptable_hard`, `agent_failure`.
2. **Given** an annotation proposing ground-truth changes, **When** the reviewer marks corpus spot-check complete, **Then** they confirm each affected answer field and required claim is supported by text in the bound filing sections referenced by expected section paths.
3. **Given** multiple annotations on the same item, **When** history is viewed, **Then** prior annotations are preserved with timestamps and are not silently overwritten.

---

### User Story 3 - Human-in-the-Loop Record Overrides (Priority: P1)

A dataset author applies approved per-item overrides to a draft bundle (extended from v2.0.0 parent), fixing the **existing 200 dev items in place** via overrides and per-slot regeneration while preserving item identities where possible, producing an auditable changelog and updated content hash before publish as v2.0.1.

**Why this priority**: Surgical fixes (wrong number, over-long claims, ambiguous question wording) must not require regenerating the entire 200-item pool or re-selecting from dev_pool.

**Independent Test**: Extend v2.0.0 to a draft, apply 3 approved overrides, re-run validation gates; verify changelog lists each item_id, fields changed, reviewer, and rationale; verify publish is blocked if any override fails validation.

**Acceptance Scenarios**:

1. **Given** an approved annotation with proposed field overrides, **When** the operator applies overrides to a draft bundle, **Then** only the specified item records change and all other items remain byte-identical.
2. **Given** applied overrides, **When** feasibility and scorability validation runs, **Then** publish is blocked if any overridden item fails existing v2 gates (bindings, macro-bindability, answer coverage, comparison rules).
3. **Given** a published quality-pass bundle derived from overrides, **When** the manifest is inspected, **Then** items content hash differs from v2.0.0, parent version is recorded, and a per-item changelog documents every change.

---

### User Story 4 - Corrective Loop for Generation Diversity (Priority: P2)

A dataset author analyzes duplicate and near-duplicate rejections from generation runs, feeds aggregated patterns into generation-spec updates, and regenerates targeted items with diversity constraints across issuers, question-type tags, and inspiration profiles.

**Why this priority**: v2.0.0 generation rejected ~40% of candidates as duplicate questions; profile quota balance in the final 200-item split does not ensure topic or issuer diversity during authoring.

**Independent Test**: Run generation on a draft with diversity governance enabled; compare duplicate-rejection share and issuer/topic spread against v2.0.0 baseline report.

**Acceptance Scenarios**:

1. **Given** a generation run, **When** duplicate or near-duplicate rejections occur, **Then** structured feedback is recorded (rejected question text, matched prior item, profile, issuer) for spec-update review.
2. **Given** diversity governance config, **When** new items are generated, **Then** the system enforces spread across issuers and question-type tags within each inspiration profile, not only equal profile counts in the final dev split.
3. **Given** a corrective spec update from aggregated duplicate feedback, **When** targeted regeneration runs for selected slots, **Then** regenerated items receive prior validation errors and human notes as regeneration constraints.

---

### User Story 5 - Substantive Comparison Ground Truth (Priority: P2)

A dataset author ensures comparison items have canonical answers that state a compared conclusion—not only that both filings mention a topic in the same section—while retaining filing-attributable claims and a cross-filing synthesis claim.

**Why this priority**: Many v2.0.0 finagentbench items pass validation with boilerplate answers (e.g. "Both filings discuss X in Item 1A") while substantive content lives only in required claims, causing brittle outcome scoring.

**Independent Test**: Validate a draft containing intentional boilerplate comparison answers; verify validation rejects them; verify human review flags remaining borderline cases.

**Acceptance Scenarios**:

1. **Given** a comparison item whose canonical answer only asserts section co-occurrence without a compared conclusion, **When** validation runs, **Then** the item is rejected with a boilerplate-comparison reason.
2. **Given** an accepted comparison item, **When** an operator reads the canonical answer, **Then** it states a substantive compared conclusion identifiable without reading required claims alone.
3. **Given** an accepted comparison item, **When** required claims are listed, **Then** they include at least one filing-attributable claim per bound filing plus one cross-filing synthesis claim.
4. **Given** human review of comparison items, **When** the canonical answer is flagged as non-informative despite passing automated checks, **Then** the item enters the override or regeneration worklist.

---

### User Story 6 - Outcome Improvement Without Full Agent Re-Run (Priority: P2)

After a dataset quality pass, a reproduction operator re-judges revised items using existing agent answers and verifies improved outcome scores for dataset-fixed items without re-running full agent reproduction.

**Why this priority**: Validating that ground-truth fixes improve scores must not require an 8-hour full reproduction for every review iteration.

**Independent Test**: Fix 10 items classified as dataset-caused zero-score; re-judge baseline variant checkpoints only; verify mean outcome score on those 10 items improves versus pre-fix scores.

**Acceptance Scenarios**:

1. **Given** revised ground truth for items with existing reproduction checkpoints, **When** selective re-judge runs, **Then** outcome scores are recomputed using stored agent answers and updated ground truth only.
2. **Given** a completed quality pass, **When** dataset-caused zero-score items are tallied, **Then** fewer than 15% of the 200 dev items remain classified as dataset-caused zero-score after review.
3. **Given** items re-judged after dataset fixes, **When** results are compared to pre-fix scores, **Then** a majority of dataset-fixed items show improved outcome scores.

---

### User Story 7 - Review Pack for Efficient Human Audit (Priority: P3)

A reviewer processes a 20-item stratified sample (or custom queue) using an exported review pack that links each item to its corpus sections and optional reproduction context.

**Why this priority**: Manual review today requires juggling multiple artifacts; a single review pack reduces audit time and improves consistency.

**Independent Test**: Export a 20-item review pack from v2.0.0; verify a reviewer can complete structural and corpus spot-checks in under 30 minutes.

**Acceptance Scenarios**:

1. **Given** a draft or published bundle, **When** the operator exports a review pack for N items, **Then** each entry includes question, profile, bindings, section paths, ground truth, required claims, and pointers to bound corpus sections in both static HTML (human review) and companion CSV (annotation import).
2. **Given** a review pack with reproduction context enabled, **When** an item has reproduction results, **Then** the pack includes outcome and ranking scores for the baseline variant.
3. **Given** a 20-item stratified sample, **When** a trained reviewer completes the pack workflow, **Then** median completion time is under 30 minutes.

---

### Edge Cases

- What happens when an override fixes ground truth but breaks macro-bindability? Publish MUST remain blocked with item-level macro failure reason.
- What happens when regeneration fails after max retries? Item stays in worklist; operator may apply manual override or exclude from dev split with documented rationale.
- What happens when reproduction results are missing for an item? Review queue exports structural review only; outcome-driven priority uses neutral default rank.
- What happens when duplicate feedback aggregates to conflicting spec recommendations? Operator resolves manually before applying generation-spec update; system does not auto-merge contradictory prompt changes.
- What happens when fewer than 200 items pass gates after quality fixes? Publish is blocked; operator MUST fix or per-slot regenerate failing items in place; dev_pool re-selection is not used.
- What happens when a reviewer classifies an item as both `gt_wrong` and `agent_failure`? System requires a single primary failure class per annotation revision; notes field captures nuance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support exporting a reproduction-driven review queue from completed reproduction output and the published dev split, prioritizing items with MRR ≥ 0.5 or nDCG@10 ≥ 0.3 and outcome score = 0 above items with weaker retrieval metrics.
- **FR-002**: System MUST support per-item annotations stored in an append-only draft sidecar (`annotations.jsonl` inside the draft bundle directory) with fields: item identifier, reviewer identity, timestamp, failure class (`gt_too_strict`, `gt_wrong`, `gt_boilerplate`, `question_ambiguous`, `claims_misaligned`, `acceptable_hard`, `agent_failure`), free-text notes, corpus spot-check status, and optional proposed field overrides; approved overrides MUST merge into dev items only on explicit apply.
- **FR-003**: System MUST preserve annotation history per item without silent overwrite of prior records.
- **FR-004**: System MUST support applying approved per-record overrides to draft bundles extended from a published parent version, improving the **existing 200 dev items in place** (not re-selecting from dev_pool); per-slot regeneration MAY replace item content but SHOULD preserve item identity when possible; each change MUST have a per-item changelog recording fields changed, reviewer, rationale, and parent item hash.
- **FR-005**: System MUST re-run existing v2 feasibility and scorability gates on any draft with applied overrides and block publish on failure.
- **FR-006**: System MUST bump items content hash and record parent version when a quality-pass bundle is published from overrides.
- **FR-007**: System MUST capture structured duplicate and near-duplicate rejection feedback during generation (rejected question, matched prior item, profile, issuer) for aggregation into generation-spec updates.
- **FR-008**: System MUST enforce generation diversity governance across issuers and question-type tags within each inspiration profile, independent of final profile-quota selection in the dev split.
- **FR-009**: System MUST support targeted item regeneration with validation feedback and human notes passed as regeneration constraints.
- **FR-010**: System MUST reject comparison items whose canonical answer is generic section co-occurrence boilerplate without a substantive compared conclusion.
- **FR-011**: System MUST require comparison items to include filing-attributable required claims per bound filing plus one cross-filing synthesis claim.
- **FR-012**: System MUST flag comparison items for human review when canonical answers are borderline non-informative per review guidelines.
- **FR-013**: System MUST support selective re-judge of revised items using stored agent answers from reproduction checkpoints, without requiring full agent re-execution.
- **FR-014**: System MUST support exporting a review pack for a configurable item set (default: 20-item stratified sample) as **static HTML plus companion CSV** with identical rows: structural fields, corpus section pointers, and optional reproduction scores; HTML is the primary human audit surface; CSV supports annotation import and queue filtering.
- **FR-015**: System MUST integrate with existing generate, publish, extend, dev pool selection, feasibility/scorability gates, and reproduction report item drill-down workflows without replacing published bundle artifacts as the evaluation lock source of truth.
- **FR-016**: System MUST keep v2.0.0 and paper-v1.0 immutable; quality improvements MUST publish as v2.0.1 extend with distinct items hash; adoption for paper reproduction MUST use a new release manifest (e.g. `paper-v1.1`) pointing at v2.0.1 with updated expected checksums.
- **FR-017**: System MAY log selective re-judge runs as secondary observability artifacts; these MUST NOT replace bundle content hashes as the canonical evaluation record.

### Key Entities

- **Review Queue Entry**: A prioritized worklist row for one dev item linking structural benchmark fields, reproduction scores (when available), and dataset-likelihood priority (MRR ≥ 0.5 or nDCG@10 ≥ 0.3 with outcome score = 0 ranks highest).
- **Item Annotation**: A timestamped human review record in draft sidecar `annotations.jsonl` for one item with failure class, notes, corpus spot-check status, and optional proposed overrides; append-only history per item; not merged into dev items until explicit apply.
- **Override Changelog Entry**: Audit record of an applied per-item change: item identifier, parent hash, changed fields, reviewer, rationale, validation outcome.
- **Duplicate Rejection Feedback**: Structured capture of a rejected near-duplicate candidate linking rejected text to the matched accepted or candidate item and sampling context (issuer, profile).
- **Diversity Governance Report**: Per-generation-run summary of issuer spread, question-type spread, duplicate rejection rate, and profile-level diversity metrics compared to configurable floors.
- **Comparison Quality Record**: Validation and human-review status for comparison items including boilerplate rejection reason or borderline flag.
- **Quality Pass Summary**: Post-review aggregate: count of items per failure class, dataset-caused zero-score share, items fixed via override vs regeneration, and re-judge outcome delta on fixed items.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Reviewers can complete structural and corpus spot-check review of a 20-item pack in under 30 minutes median time.
- **SC-002**: After a quality pass on v2.0.0 lineage, fewer than 15% of dev items remain classified as dataset-caused zero-outcome-score (`gt_too_strict`, `gt_wrong`, `gt_boilerplate`, `claims_misaligned`, or `question_ambiguous`).
- **SC-003**: A majority of items fixed via override or regeneration show improved outcome scores on selective re-judge without full agent re-execution.
- **SC-004**: A subsequent generation run with diversity governance shows duplicate-rejection share at least 10 percentage points lower than the v2.0.0 baseline (~40%) while maintaining automated validation pass rate at or above the v2.0.0 candidate acceptance rate.
- **SC-005**: Zero accepted comparison items in a quality-pass draft use boilerplate-only canonical answers as measured by automated validation and human audit of a stratified comparison sample.
- **SC-006**: Dev split issuer and question-type diversity metrics (unique issuers per profile, unique question-type tags per profile) improve versus v2.0.0 baseline in a quality-pass or diversity-governed regeneration run.
- **SC-007**: Every applied override has a corresponding changelog entry and updated items content hash before publish; v2.0.0 parent bundle remains unchanged on disk.

## Assumptions

- v2.0.0 / paper-v1.0 reproduction checkpoints exist locally or can be reproduced to seed the review queue.
- Reviewers have access to the bundled corpus sections referenced by expected section paths for spot-checks.
- Existing v2 publish gates (200 items, answer coverage, multi-filing floor, macro-bindability, operator sign-off) remain in force for quality-pass bundles unless explicitly extended in a follow-on spec.
- Default quality-pass strategy is **in-place patch** on the existing 200 dev items (overrides + per-slot regeneration), published as **v2.0.1 extend** from v2.0.0 parent; dev_pool re-selection is out of scope unless an item is explicitly excluded with documented rationale.
- Paper adoption requires a **new paper release manifest** (e.g. paper-v1.1) with updated expected checksums; paper-v1.0 remains immutable for audit comparison.
- Agent-side outcome failures are out of scope for dataset fixes; annotations distinguish agent failure from dataset defects.
- Selective re-judge reuses the same external judge criterion as paper reproduction (value alignment on ground truth).

## Dependencies

- Feature 011 (judge-eval-dataset): generation, validation, publish, extend CLI and bundle layout.
- Feature 017 (custom-judge-v2): v2 gates, comparison structured template, feasibility/scorability reports, publish audit.
- Feature 012–014: reproduction run-all, judge-batch, report item drill-down.
- Feature 015: re-judge workflow for selective outcome re-scoring.
- Feature 012: new paper-v1.1 release manifest and expected checksums when quality-pass bundle is adopted.
