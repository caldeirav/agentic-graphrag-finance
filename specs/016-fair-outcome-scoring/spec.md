# Feature Specification: Fair Reproduction Outcome Scoring

**Feature Branch**: `016-fair-outcome-scoring`

**Created**: 2026-06-07

**Status**: Draft

**Input**: Fix reproduction outcome scoring fairness so graph-full beats flat-chunk on HTML narrative outcome accuracy while ranking metrics stay unchanged. On HTML-stratum items, flat-chunk headline outcome_accuracy (0.48) exceeds graph-full (0.42) even though MRR/nDCG strongly favor graph-full. Root causes: stale judge verdicts missing ground-truth-aware criteria with synthesis-only fallback; flat-chunk verbatim chunk-dump answers gaming grounding scores; flat-chunk judged on graph trajectory criteria it does not perform; qualitative answer ground truth and comparison/reference items poorly suited to current aggregation. Depends on features 012–015 (reproduction kit, deferred judge, results viewer, eval validity). Out of scope: changing ranking metric definitions; new model endpoints; re-running full agent queries for paper-v1.0.

## Clarifications

### Session 2026-06-07

- Q: When `value_alignment` is missing from a stored judge verdict for an answer-GT item, how should outcome contribute? → A: Count as **zero** for that item in outcome_accuracy (do not exclude from denominator) so incomplete judge coverage is visible in aggregate scores and investigation notes.
- Q: Should flat-chunk be judged on graph trajectory criteria? → A: **No** — flat-chunk uses a retrieval-focused criterion set only; graph variants retain full trajectory criteria.
- Q: Must existing paper-v1.0 checkpoints be re-scored? → A: **Yes** — operators re-run judge-batch (with force-rescore when needed) after deploy; idempotent resume must require complete criterion coverage per item type.
- Q: For the existing custom-judge v1.0.0 dev split (~200 items), what is in scope for dataset quality fixes? → A: **New bundle version** — publish `v1.1.0` with required-claims, rubric-only routing, and feasibility fixes; update `paper-v1.0` release manifest to point at the new bundle path (v1.0.0 remains unchanged for audit/history).
- Q: Should tightening the resume gate also bump judge version to v3? → A: **Yes** — resume skip requires judge version ≥ v3 **and** full criterion set for the item's ground-truth type; all v2 verdicts are re-judged on next batch (force-rescore optional for v3 items).
- Q: If SC-001 (graph-full outcome > flat-chunk) is not met after full implementation, how should the feature be treated? → A: **Target with escalation** — ship scoring/rubric/dataset fixes; SC-001 failure emits a documented investigation note and follow-up task, not a release block.
- Q: After publishing v1.1.0 and updating the manifest, what must operators re-run? → A: **Selective re-run** — re-judge + export for items unchanged in v1.1.0; re-run agent variants only for items with question or binding changes (documented in bundle changelog).
- Q: Which answer-GT items must include structured required-claims in v1.1.0? → A: **All non-numeric answer-GT items** — numeric or short-label GT (e.g., FinanceBench percentages) remain single value-alignment targets; narrative items receive scorable claim lists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy Outcome Accuracy (Priority: P1)

A research reproduction operator re-scores an existing paper reproduction output and exports headline tables where outcome accuracy reflects answer correctness, not merely whether an answer quotes its own citations. Graph-full outcome on HTML narrative items exceeds flat-chunk, consistent with ranking metrics.

**Why this priority**: Paper headline outcome comparisons are misleading today; this blocks credible ablation claims even when retrieval metrics are correct.

**Independent Test**: Re-score `paper-v1.0` dev split (all five variants), re-export tables, and verify graph-full outcome_accuracy strictly exceeds flat-chunk on the HTML evidence stratum and on the pooled headline; MRR and nDCG@10 rankings remain unchanged from pre-fix baselines (same agent answers, same relevance labels).

**Acceptance Scenarios**:

1. **Given** a benchmark item with answer ground truth and a completed judge verdict containing `value_alignment`, **When** outcome_accuracy is computed, **Then** the item score equals `value_alignment` only (no fallback to synthesis or grounding scores).
2. **Given** a benchmark item with answer ground truth and a judge verdict missing `value_alignment`, **When** outcome_accuracy is computed, **Then** the item contributes zero.
3. **Given** a completed re-score of paper-v1.0, **When** headline tables are exported, **Then** graph-full outcome_accuracy is greater than flat-chunk on the HTML stratum and globally.
4. **Given** the same reproduction checkpoints before and after this feature (agent answers unchanged), **When** ranking metrics are compared, **Then** MRR, MAP, and nDCG@10 per variant differ by less than 0.001 (unchanged).

---

### User Story 2 - Complete Judge Coverage on Resume (Priority: P1)

An operator interrupts a long judge-batch run and resumes later without retaining stale partial verdicts that omit ground-truth-aware criteria.

**Why this priority**: Feature 015 resume skip on judge version plus hydrated evidence preserved incomplete v2 verdicts, causing systemic zero rubric alignment and synthesis fallback for answer-GT items.

**Independent Test**: Seed a fixture with v2 verdicts containing only trajectory criteria; run judge-batch without force-rescore; verify items with answer or rubric ground truth are re-judged and stored verdicts include all required criteria for that item type.

**Acceptance Scenarios**:

1. **Given** a stored verdict at judge version v2 (or v2 with hydrated evidence but incomplete criteria), **When** judge-batch runs, **Then** that item is judged again and stored at judge version v3 with the full criterion set.
2. **Given** a stored verdict at judge version ≥ v3 with all criteria required for the item's ground-truth type, **When** judge-batch runs without force-rescore, **Then** that item is skipped.
3. **Given** a full re-score completes, **When** results are inspected, **Then** fewer than 5% of answer-GT items lack `value_alignment` in stored verdicts.

---

### User Story 3 - Judge Rubrics That Penalize Chunk-Dump Gaming (Priority: P2)

An evaluation engineer configures judge rubrics so dense-retrieval baselines cannot earn high outcome scores by concatenating verbatim chunks without answering the question.

**Why this priority**: Flat-chunk's answer format structurally satisfies grounding rubrics while failing semantically; rubrics must distinguish citation overlap from question answering.

**Independent Test**: Unit-test judge prompt/rubric contracts and integration samples where flat-chunk chunk-dump answers receive low `value_alignment` and low `synthesis_grounding` when they do not address the question or use wrong-filing evidence.

**Acceptance Scenarios**:

1. **Given** an answer that is only verbatim chunk text without addressing the question, **When** judged for synthesis grounding, **Then** the score is zero.
2. **Given** cited evidence from the wrong issuer or filing relative to the question bindings, **When** judged, **Then** value alignment and synthesis grounding reflect the mismatch (near zero).
3. **Given** qualitative answer ground truth requiring multiple claims, **When** judged for value alignment, **Then** scoring reflects claim coverage, not substring overlap with chunk headers.
4. **Given** an abstention or "cannot answer" response when cited evidence supports a substantive answer per ground truth, **When** judged, **Then** value alignment and claim presence are zero.

---

### User Story 4 - Higher-Quality Benchmark Items (Priority: P2)

A dataset author publishes custom-judge items where ground truth is scorable and corpus-feasible, especially for comparison and cross-filing reference questions.

**Why this priority**: Long narrative answer strings and loose comparison GT make outcome metrics subjective; infeasible bindings produce macro failures scored inconsistently.

**Independent Test**: Publish custom-judge bundle `v1.1.0` with validated dev split; update release manifest bundle path; run generation validation — zero items with comparison question tags pass validation without required comparison partners in expected bindings; rubric-only routing applied to configured question-type tags.

**Acceptance Scenarios**:

1. **Given** an answer-GT item whose ground truth is non-numeric (narrative or multi-claim), **When** the item is published in v1.1.0, **Then** it includes structured required-claims metadata scorable by the judge; numeric or short-label GT items do not require required-claims.
2. **Given** a cross-filing comparison, multi-hop narrative, or reference-following question type, **When** the item is published, **Then** grading uses rubric ground truth (claim presence) rather than a loose answer string.
3. **Given** an item with expected bindings, **When** generation validation runs, **Then** referenced filings and comparison partners are present in the corpus slice and failures are reported before publish.

---

### User Story 5 - Interpretable Stratified Reporting (Priority: P3)

A paper author opens the reproduction report and sees outcome accuracy broken down by inspiration profile and evidence stratum, with flat-chunk judged fairly on retrieval-appropriate criteria.

**Why this priority**: Pooled headline tables hide profile and stratum effects; operators need interpretable views without misleading single-number comparisons.

**Independent Test**: Generate report from a full five-variant reproduction; confirm variant-aware judge criteria for flat-chunk; profile and stratum outcome sections are present; investigation report does not flag rubric alignment zero after complete re-score.

**Acceptance Scenarios**:

1. **Given** a flat-chunk variant result, **When** judged, **Then** trajectory coherence and routing criteria are not required; retrieval fidelity, answer quality, and ground-truth criteria apply.
2. **Given** exported tables and HTML report, **When** an operator views outcome metrics, **Then** breakdowns by inspiration profile and primary evidence source are visible alongside pooled headline.
3. **Given** a completed re-score with rubric-GT items, **When** the investigation report renders, **Then** rubric alignment is non-zero and the RUBRIC_ALIGNMENT_ZERO pattern is absent.

---

### Edge Cases

- Item has both answer and rubric ground truth: outcome uses value_alignment; rubric alignment uses claim_presence independently.
- Item has rubric only: excluded from outcome_accuracy numerator (existing behavior); included in rubric_alignment.
- Judge API returns partial criteria JSON: verdict rejected or retried; item not marked complete with incomplete criterion set.
- flat-chunk retrieves zero chunks: abstention scored consistently with graph variants when ground truth expects an answer.
- HTML stratum with fewer than ten eligible items: stratum row carries low-n indicator (existing 015 behavior).
- Operator runs judge-batch without re-export: tables remain stale; documentation warns export is required after re-score.
- Operator retains old `v1.0.0` bundle path in manifest: SC-006 and dataset-quality acceptance do not apply until manifest points to `v1.1.0`.
- SC-001 not met after v3 re-score: feature still ships; report surfaces `OUTCOME_ORDERING_REGRESSION` for operator follow-up.
- Item revised in v1.1.0 changelog: existing agent answers invalid until that item is re-run across affected variants.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Outcome accuracy MUST use only `value_alignment` for items with answer ground truth; synthesis grounding MUST NOT substitute when value alignment is absent (score zero instead).
- **FR-002**: Rubric alignment MUST use only `claim_presence` for items with rubric ground truth; absent claim presence scores zero.
- **FR-003**: Judge-batch resume skip MUST require judge version ≥ v3 **and** stored verdicts that include every criterion required for the item's ground-truth type and variant (not v2 with hydrated evidence alone).
- **FR-004**: Re-judge workflow MUST remain idempotent for v3 complete verdicts; force-rescore MUST bypass skip for operator overrides including v3 items.
- **FR-005**: Judge rubrics MUST penalize verbatim chunk-dump answers that do not address the question, wrong-issuer or wrong-filing citations, and header-only fragment matches without semantic coverage.
- **FR-006**: Judge rubrics MUST define value alignment for qualitative answer ground truth as claim coverage against expected substance, not substring overlap with retrieved chunk text.
- **FR-007**: Dataset generation MUST attach structured required-claims to all non-numeric answer-GT items in v1.1.0 and MUST route configured comparison, multi-hop, and reference-following question types to rubric-only grading; numeric/short-label answer-GT items remain single-target value alignment without required-claims.
- **FR-008**: Dataset generation MUST validate corpus feasibility of expected bindings and relevant chunk labels before publish (comparison partners present, referenced filings in slice); validation gates publish of `v1.1.0`.
- **FR-013**: Release manifest for `paper-v1.0` MUST be updated to reference the new custom-judge bundle path (`v1.1.0`); existing `v1.0.0` bundle remains available for historical comparison.
- **FR-014**: Bundle `v1.1.0` publish MUST include a changelog listing items with question or binding changes vs v1.0.0; reproduction docs MUST describe selective re-run (re-judge-only for unchanged items, agent re-run for changed items).
- **FR-009**: Flat-chunk variant judging MUST use a retrieval-focused criterion set (retrieval fidelity, answer quality, and applicable ground-truth criteria) excluding graph trajectory criteria.
- **FR-010**: Reproduction export and HTML report MUST surface outcome accuracy by inspiration profile and by primary evidence source with clear labels; pooled headline remains available but not the only view.
- **FR-011**: Investigation notes MUST flag incomplete judge criterion coverage when answer-GT items lack value alignment after a claimed-complete re-score, and MUST flag `OUTCOME_ORDERING_REGRESSION` when SC-001 is not satisfied after v3 re-score on bundle v1.1.0.
- **FR-012**: Ranking metrics (MRR, MAP, nDCG@10) MUST NOT change as a result of this feature (judge and export scoring only).

### Key Entities

- **Outcome score**: Per-item headline contribution derived from judge verdict; answer-GT items map exclusively to value alignment.
- **Rubric alignment score**: Per-item contribution from claim presence on rubric-GT items.
- **Judge criterion set**: Required rubric dimensions per item, varying by ground-truth type and system variant (graph vs flat-chunk).
- **Required claims**: Structured list of factual claims attached to non-numeric answer-GT benchmark items for machine-checkable grading; omitted for numeric or short-label ground truth.
- **Evidence stratum**: Primary evidence source label (html, xbrl, mixed, unknown) assigned from relevance chunk ids.
- **Inspiration profile**: Dataset lineage tag (e.g., financebench, finagentbench, finder) for profile-scoped metrics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After re-score on paper-v1.0 dev split (manifest on bundle v1.1.0), graph-full outcome_accuracy strictly exceeds flat-chunk on the HTML evidence stratum and on the pooled headline row. If not met after complete implementation, investigation report MUST emit an `OUTCOME_ORDERING_REGRESSION` note with variant deltas and example item ids; feature delivery is not blocked.
- **SC-002**: Ranking metrics (MRR, MAP, nDCG@10) per variant differ by less than 0.001 from pre-fix baselines on the same checkpoints (agent outputs unchanged).
- **SC-003**: After complete re-score, rubric_alignment is greater than zero for every variant with rubric-GT items; investigation report does not emit RUBRIC_ALIGNMENT_ZERO.
- **SC-004**: Fewer than 5% of answer-GT items lack value_alignment in stored v3 verdicts after a complete re-score.
- **SC-005**: Paired HTML answer-GT items where flat-chunk outcome exceeded graph-full solely due to synthesis grounding (graph synthesis lower, flat-chunk synthesis higher, both missing value alignment) decrease by at least 80% compared to the pre-fix paper-v1.0 checkpoint.
- **SC-006**: Custom-judge bundle `v1.1.0` dev split validation reports zero items with comparison or reference-following tags that fail corpus-feasibility checks; release manifest references `v1.1.0`.

## Assumptions

- Feature 015 stratified export (`by_evidence_source`, `by_profile`, `variant_delta_by_source`) remains the foundation; this feature corrects scoring inputs and improves report prominence, not stratum assignment rules.
- Judge version v3 denotes post-fix complete verdicts; v2 checkpoints are always re-judged once after deploy (no partial v2 resume).
- Answer-GT items missing value_alignment after re-score count as zero in outcome_accuracy (denominator unchanged) so aggregate scores reflect incomplete judging.
- "Answer quality" is a new judge criterion for retrieval baselines, scored on whether the response addresses the question using retrieved evidence substantively.
- paper-v1.0 reproduction checkpoints remain valid for agent answers on items unchanged in v1.1.0; operators run judge-batch and export-tables after deploying scoring fixes; items with question or binding changes in v1.1.0 require selective agent re-run before re-judge.
- Question-type tags for rubric-only routing already exist or will be extended in the custom-judge schema; quality fixes ship as bundle `v1.1.0` while `v1.0.0` remains immutable for audit.
- Reproduction acceptance uses manifest-updated bundle path; operators re-score against checkpoints produced under the updated bundle context.
- External judge model and configuration path remain the project's existing Gemini judge setup; only rubric text and criterion selection change.

## Dependencies

- **015-repro-eval-validity** (merged): stratum export, judge-batch resume, re-judge workflow, investigation report aggregation.
- **013-benchmark-eval-acceleration**: deferred judge-batch, flat-chunk baseline variant.
- **011-judge-eval-dataset**: custom-judge bundle schema and generation pipeline.
