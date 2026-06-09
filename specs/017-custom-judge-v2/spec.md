# Feature Specification: Custom-Judge Bundle v2.0 and Unified Task Success

**Feature Branch**: `017-custom-judge-v2`

**Created**: 2026-06-02

**Status**: Draft

**Input**: Re-author custom-judge bundle v2.0 and paper-v2.0 release for a unified 200-item task_success metric. Goals: (1) every dev item has scorable ground_truth.answer (no rubric-only headline path); non-numeric answers require required_claims; (2) comparison and multi-filing items use comparison_structured answers (e.g. both filings discuss X in Item 7) with derived atomic claims instead of rubric-only grading; (3) greenfield regenerate or heavily re-author items against a refreshed frozen corpus—not incremental migrate from v1.2.0; new corpus_hashes, items_hash, relevance_labels_hash → new paper-v2.0 release lock with full agent re-run on all five variants; (4) headline task_success = mean value_alignment over n=200 (missing VA = 0), single judge criterion for all items; keep v1.2.0 immutable. In scope: bundle contract, generation/validation pipeline, feasibility gates, release manifest, export/report contract, operator quickstart. Out of scope: changing MRR/nDCG definitions; new model endpoints; retroactive paper-v1.0 score updates.

## Clarifications

### Session 2026-06-02

- Q: Should v2.0 reuse the v1.2.0 frozen corpus or refresh filings? → A: **Refreshed corpus** — v2.0 bundles a newly sampled and materialized corpus slice with updated content hashes; v1.2.0 corpus remains immutable for audit.
- Q: How should comparison items be scored when one filing mentions a topic and the other does not? → A: **Structured answer + atomic claims** — the canonical answer states what both filings discuss; required_claims decompose per-filing coverage so partial credit is possible via claim support, not a separate rubric-only path.
- Q: What happens to FinDER-style items that previously relied on rubric-only grading? → A: **Re-author to answer-GT** — each item receives a concise retrieval-target answer plus required_claims where non-numeric; items that cannot meet v2 scorability gates are replaced in the v2 pool, not carried forward as rubric-only.
- Q: What v1.2.0 content may carry into v2.0? → A: **Net-new pool** — no v1.2.0 questions, bindings, or item IDs are reused; v2.0 is authored entirely from the refreshed corpus with new item identities. v1.2.0 changelog may document thematic lineage for audit only.
- Q: Should macro-bindability be a blocking publish gate for all v2.0 items? → A: **Blocking for all 200 items** — every accepted item must pass macro binding validation against the bundled corpus before publish.
- Q: What is the minimum count of comparison or multi-filing items in the v2.0 dev split? → A: **≥40 items (20%)** — publish is blocked if fewer than 40 accepted items are comparison-tagged or require multi-filing bindings.
- Q: What operator human review is required before v2.0 publish? → A: **Reports + 10% audit** — operator signs off on feasibility and scorability reports and manually reviews 20 stratified sample items before explicit publish approval.
- Q: For paper-v2.0 reproduction reports, should rubric_alignment be shown? → A: **Omit entirely** — v2.0 exports and reports exclude rubric_alignment rows; task_success (value alignment, n=200) is the sole headline outcome metric.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Headline Success Over Full Dev Split (Priority: P1)

A research reproduction operator runs the paper-v2.0 kit and exports headline tables where **task_success** is computed over all 200 dev items using a single ground-truth-aware judge criterion (value alignment), without splitting the pool into answer-GT and rubric-only subsets.

**Why this priority**: The current v1.2.0 headline metric blends two judge criteria across unequal pools (~61 answer-GT vs ~139 rubric-only), making n=200 comparisons misleading and blocking credible ablation claims on outcome.

**Independent Test**: Publish a v2.0 draft bundle passing feasibility gates; run judge-batch on fixture answers; export tables and verify task_success denominator is 200 and each item score derives from value alignment only (zero when absent).

**Acceptance Scenarios**:

1. **Given** a published v2.0 dev split with 200 accepted items, **When** headline metrics are exported, **Then** task_success reports n=200 and equals the mean value-alignment score across all eligible items.
2. **Given** a v2.0 item with a completed judge verdict missing value alignment, **When** task_success is computed, **Then** that item contributes zero (not excluded from the denominator).
3. **Given** the same reproduction checkpoints evaluated against v1.2.0 and v2.0 bundles, **When** ranking metrics are compared, **Then** MRR, MAP, and nDCG@10 per variant are unchanged in definition and remain reportable alongside the new outcome metric.

---

### User Story 2 - Answer-GT Coverage on Every Benchmark Item (Priority: P1)

A dataset author publishes custom-judge bundle v2.0 where every dev item includes a non-empty scorable answer ground truth, with structured required-claims on non-numeric answers, so operators never depend on rubric-only grading for headline success.

**Why this priority**: Rubric-only routing was a v1.x compromise for comparison and retrieval items; v2.0 exists to make every item objectively scorable the same way.

**Independent Test**: Run publish validation on v2.0 draft; verify zero items with null or empty answer ground truth; verify every non-numeric answer has 2–8 atomic required claims; verify publish is blocked otherwise.

**Acceptance Scenarios**:

1. **Given** a v2.0 benchmark item accepted into the dev split, **When** an operator inspects ground truth, **Then** `ground_truth.answer` is present and non-empty.
2. **Given** a v2.0 item whose answer is narrative or multi-claim prose, **When** validation runs, **Then** the item includes 2–8 atomic required-claims suitable for graded value alignment.
3. **Given** a v2.0 item whose answer is numeric or a short canonical label, **When** validation runs, **Then** required-claims are omitted and value alignment targets the single answer string.
4. **Given** a draft item that would have been rubric-only under v1.x routing, **When** v2.0 validation runs, **Then** the item is rejected unless re-authored with answer ground truth meeting scorability rules.

---

### User Story 3 - Structured Ground Truth for Comparison and Multi-Filing Items (Priority: P1)

A dataset author generates comparison and multi-filing benchmark items where the canonical answer follows a structured template (e.g., both bound filings discuss a named topic in a named section) and required-claims reference each filing separately, instead of relying on free-form rubric text for headline grading.

**Why this priority**: Comparison items were the largest rubric-only cohort in v1.x and are central to agentic retrieval evaluation; they must be first-class citizens in the unified metric.

**Independent Test**: Sample all v2.0 items tagged as comparison or multi-filing; verify answer type is comparison-structured, bindings include ≥2 accessions, and required-claims include at least one claim per bound filing plus a cross-filing comparison claim.

**Acceptance Scenarios**:

1. **Given** a comparison question requiring two filings, **When** the item is published in v2.0, **Then** expected bindings list at least two accessions present in the bundled corpus.
2. **Given** a published comparison item, **When** an operator reads the canonical answer, **Then** it explicitly references both bound filings and the compared topic and section (or equivalent structural anchor).
3. **Given** a published comparison item, **When** required-claims are listed, **Then** claims are atomic, filing-attributable, and sufficient for partial credit when only one filing’s evidence supports a sub-claim.
4. **Given** a multi-filing narrative item that is not a numeric metric comparison, **When** published, **Then** it uses the same answer-plus-claims model rather than rubric-only grading.

---

### User Story 4 - Greenfield v2.0 Bundle and paper-v2.0 Release Lock (Priority: P2)

A release engineer produces bundle v2.0 as a net-new item pool against a refreshed frozen corpus, publishes it under a new paper-v2.0 release manifest with new content hashes, and runs a full agent reproduction on all five system variants without selective skip rules from prior bundle changelogs.

**Why this priority**: Incremental migration from v1.2.0 preserved infeasible bindings and mixed grading semantics; a new release lock makes reproduction auditable and comparable only within the v2.0 lineage.

**Independent Test**: Publish v2.0.0; verify manifest records new corpus, items, and relevance-label hashes distinct from paper-v1.0; run full reproduction; verify v1.2.0 bundle and paper-v1.0 manifest remain unchanged.

**Acceptance Scenarios**:

1. **Given** a completed v2.0 generation run, **When** the operator publishes the bundle, **Then** the manifest version is 2.0.0, parent lineage to v1.2.0 is documented for audit, and v1.2.0 artifacts are not modified.
2. **Given** paper-v2.0 release manifest, **When** an operator inspects lock fields, **Then** corpus hashes, items hash, and relevance-labels hash differ from paper-v1.0 and are required for reproduction acceptance.
3. **Given** paper-v2.0 reproduction, **When** all five variants run, **Then** every dev item is executed across variants (no selective agent re-run exemptions based on v1.x changelog).
4. **Given** a third party with the published bundle only, **When** they reproduce sampling and materialization from documented config and seed, **Then** they obtain the same published content hashes without live EDGAR access at evaluation time.
5. **Given** a v2.0 draft meeting all automated gates, **When** an operator completes publish approval, **Then** they have signed off on feasibility and scorability reports and completed a manual audit of 20 stratified sample items (10% of the dev split).

---

### User Story 5 - Feasibility and Scorability Gates Before Publish (Priority: P2)

An evaluation engineer validates that every v2.0 item is corpus-feasible (bindings, section reachability, macro-bindable) and judge-scorable before publish, receiving a blocking report for any item that would fail in reproduction or produce ambiguous headline grading.

**Why this priority**: v1.x feasibility fixes were retroactive; v2.0 must fail closed at generation time so the unified metric is trustworthy on first publish.

**Independent Test**: Run validation on a v2.0 draft containing intentional infeasible items; verify publish is blocked with item-level reasons; fix items and verify clean publish.

**Acceptance Scenarios**:

1. **Given** a v2.0 draft item whose expected section paths do not resolve in the bundled graph, **When** feasibility validation runs, **Then** publish is blocked and the item id and reason are reported.
2. **Given** a comparison item with fewer than two bound accessions, **When** validation runs, **Then** publish is blocked.
3. **Given** a v2.0 draft where fewer than 200 items pass all gates, **When** publish is attempted, **Then** publish fails with a clear item-count gate message.
4. **Given** a v2.0 draft with fewer than 40 comparison or multi-filing items among accepted items, **When** publish is attempted, **Then** publish fails with a multi-filing floor gate message.
5. **Given** a v2.0 draft meeting all gates, **When** feasibility and scorability reports are emitted, **Then** operators can review per-item binding, reachability, answer-type coverage, macro-bindability, and profile mix (including multi-filing count ≥40) before explicit publish approval.
6. **Given** any v2.0 draft item whose expected bindings fail macro binding validation against the bundled corpus, **When** feasibility validation runs, **Then** publish is blocked and the item id and macro failure reason are reported.

---

### User Story 6 - Reproduction Reports Reflect v2.0 Metric Semantics (Priority: P3)

A paper author opens the reproduction report and sees task_success labeled as a unified n=200 value-alignment metric, with no rubric_alignment headline row for v2.0 runs, and stratum breakdowns still available for interpretation.

**Why this priority**: Operators must not misread v2.0 tables using v1.x mental models (split pools, rubric-only exclusions).

**Independent Test**: Generate report from a paper-v2.0 reproduction fixture; verify primary metric row shows task_success n=200 and documents single-criterion semantics; verify MRR/nDCG rows unchanged.

**Acceptance Scenarios**:

1. **Given** a paper-v2.0 reproduction export, **When** an operator views headline tables, **Then** task_success is listed as the sole headline outcome metric with n=200 and a note that all items use answer ground truth graded by value alignment, and **rubric_alignment is not present**.
2. **Given** a paper-v2.0 reproduction export, **When** stratum tables render, **Then** outcome breakdowns by inspiration profile and evidence stratum use task_success (or value-alignment-derived outcome) without rubric-only exclusions or rubric_alignment rows.
3. **Given** a reproduction run pinned to paper-v1.0 / v1.2.0, **When** reports render, **Then** v1.x metric semantics (including rubric_alignment where applicable) remain available and are not altered retroactively.

---

### Edge Cases

- Item has both answer and auxiliary rubric text: headline uses value alignment on answer and claims; rubric text is non-authoritative metadata only and is not exported as rubric_alignment for paper-v2.0.
- Judge returns partial value alignment with some required claims unsupported: item score reflects graded claim coverage per existing value-alignment policy; item still counts in n=200.
- Agent abstains on a feasible v2.0 item: value alignment is zero; item remains in denominator.
- v2.0 item covers a similar evaluation intent as a v1.2.0 item: v2.0 uses a new item id; optional changelog notes thematic lineage only; v1.2.0 item remains in the immutable v1.2.0 bundle.
- FinDER-profile item cannot be re-authored with answer-GT: item is rejected or replaced during generation; dev split still reaches 200 accepted items via quota backfill.
- Comparison item where topic appears in different sections across filings: structured answer names both sections; claims capture per-filing section attribution.
- Operator attempts to publish v2.0 by migrating v1.2.0 in place: workflow must produce a new version directory and manifest, not overwrite v1.2.0.
- Agent macro binding fails on a published-feasible item at reproduction time: item should have been blocked at publish; such cases indicate a validation regression and invalidate publish acceptance.
- Single-filing item with valid section reachability but invalid macro anchor: publish blocked — macro-bindability is required for all items, not only comparison types.
- Full reproduction interrupted mid-run: resume rules follow existing reproduction kit behavior; paper-v2.0 lock still requires eventual full variant coverage for acceptance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST publish custom-judge bundle version 2.0.0 as a distinct artifact lineage from v1.2.0; v1.2.0 MUST remain immutable after v2.0 publish.
- **FR-002**: Every accepted item in the v2.0 dev split MUST include non-null, non-empty `ground_truth.answer`.
- **FR-003**: Every v2.0 item with non-numeric answer ground truth MUST include 2–8 atomic `ground_truth.required_claims` suitable for graded value alignment.
- **FR-004**: Every v2.0 item tagged as comparison or requiring multi-filing bindings MUST use comparison-structured answer ground truth, bind ≥2 corpus accessions, and include required-claims attributing content to each bound filing.
- **FR-005**: System MUST NOT use rubric-only grading for headline task_success on v2.0 items; rubric text MAY exist as auxiliary judge context but MUST NOT be the primary ground-truth target.
- **FR-006**: v2.0 items MUST be produced as a **net-new pool** against a refreshed frozen corpus — no v1.2.0 question text, expected bindings, or item IDs may be reused; incremental in-place migration from v1.2.0 is forbidden.
- **FR-007**: v2.0 bundle manifest MUST record new corpus content hashes, items hash, and relevance-labels hash distinct from paper-v1.0 / v1.2.0.
- **FR-008**: paper-v2.0 release manifest MUST pin bundle v2.0.0, refreshed hashes, eval split, five variant ids, and require full agent re-execution on all dev items for all variants.
- **FR-009**: Headline task_success for paper-v2.0 MUST equal the mean value-alignment score over all 200 eligible dev items, counting missing value alignment as zero.
- **FR-010**: Publish workflow MUST block v2.0 release when any item fails feasibility gates (answer coverage, required-claims, comparison bindings, corpus reference, section reachability, question–binding alignment, macro-bindability for every item, minimum item count, **minimum 40 comparison or multi-filing items**).
- **FR-011**: Generation and validation pipeline MUST emit operator-reviewable feasibility and scorability reports before explicit publish approval; publish MUST require operator sign-off on those reports plus completion of a **10% stratified manual item audit (20 items)** documented in the publish record.
- **FR-012**: Reproduction export and report for paper-v2.0 MUST document task_success semantics (n=200, single value-alignment criterion) as the sole headline outcome metric, **omit rubric_alignment rows entirely**, and MUST NOT alter MRR/nDCG definitions.
- **FR-013**: v2.0 authoring MUST preserve inspiration-profile quotas and question-type diversity comparable to v1 targets (FinanceBench-, FinDER-, and FinAgentBench-style coverage) while meeting answer-GT coverage rules; **at least 40 of 200 accepted items MUST be comparison-tagged or require multi-filing bindings**.
- **FR-014**: Item changelog for v2.0 MUST document the net-new v2.0 pool and MAY note thematic lineage to v1.2.0 evaluation intents for audit; v1.2.0 files MUST NOT be modified and v1.2.0 item IDs MUST NOT appear in v2.0 items.

### Key Entities

- **Benchmark Item (v2.0)**: A dev-split evaluation question with mandatory answer ground truth, optional auxiliary rubric, required-claims when non-numeric, expected bindings, expected section paths, inspiration profile, and answer-type classification (numeric, short_label, narrative, comparison_structured).
- **Comparison-Structured Answer**: Canonical answer template tying a topic and structural anchor (e.g., Item 7 MD&A) to each bound filing; paired with atomic required-claims for per-filing and cross-filing coverage.
- **Bundle Manifest (v2.0.0)**: Version metadata, parent lineage, item count, content hashes, corpus bundle reference, generation provenance, and publish status.
- **Feasibility Report**: Pre-publish gate results listing blocked items with reasons (bindings, reachability, claims, alignment, **macro-bindability**).
- **Scorability Report**: Pre-publish confirmation that every item is judge-scorable via answer ground truth and claims without rubric-only interpretation.
- **paper-v2.0 Release Lock**: Release manifest binding bundle v2.0.0, hash set, variant list, and full-reproduction policy for third-party audit.
- **task_success (v2.0)**: Headline outcome metric — mean value alignment over n=200 dev items, zero when alignment absent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Published v2.0 dev split contains exactly 200 accepted items, 100% with non-empty answer ground truth (0 rubric-only headline items).
- **SC-002**: 100% of non-numeric v2.0 answers include 2–8 required-claims at publish time; 0 publish gate failures on required-claims for accepted items.
- **SC-003**: 100% of comparison-tagged v2.0 items bind ≥2 corpus accessions and use comparison-structured answers with filing-attributable claims; **the dev split contains at least 40 comparison or multi-filing items**.
- **SC-004**: paper-v2.0 release manifest corpus, items, and relevance-label hashes are all distinct from paper-v1.0 / v1.2.0 values.
- **SC-005**: Reproduction export for paper-v2.0 reports task_success with n=200 derived solely from value-alignment scores (missing scores count as zero).
- **SC-006**: A full paper-v2.0 reproduction completes agent execution on all five variants across all 200 dev items without selective v1.x changelog skip rules.
- **SC-007**: Operators can publish v2.0 only after feasibility and scorability reports show zero blocked items (including zero macro-bindability failures across all 200 items); attempted publish with any blocked item fails with an actionable report.
- **SC-008**: Third-party operators following published generation config, seed, and bundled corpus reproduce the published v2.0 content hashes without live EDGAR fetches at evaluation time.

## Assumptions

- v1.2.0 and paper-v1.0 remain the audit baseline for prior reproductions; v2.0 does not retroactively change their scores or manifests.
- Refreshed corpus sampling follows the existing committed issuer allowlist and seeded sampling governance from prior custom-judge generation (new accession set, new hashes).
- Value-alignment grading policy for required-claims carries forward the graded partial-credit semantics established in v1.2.0 / judge v3.1 (no new judge model endpoint required).
- Ranking metrics (MRR, MAP, nDCG@10) and structural trajectory metrics retain existing definitions; only headline outcome aggregation changes for paper-v2.0.
- Draft-then-explicit-publish workflow from prior dataset generation remains the operator approval gate, including sign-off on automated reports and a 10% stratified manual item audit before publish.
- Dev split size remains 200 items; train or other splits are out of scope unless added in a follow-on feature.
- Five system variants (graph-full, flat-chunk, ablation-no-macro, ablation-no-walker, ablation-xbrl-only) remain the paper reproduction set.
- Items that cannot meet v2.0 scorability during generation are rejected and backfilled with new net-new items so quotas and item count still satisfy publish gates.
- v2.0 is a net-new item pool; similarity to v1.2.0 items is coincidental and not a reuse or migration relationship.

## Dependencies

- Feature 011 (judge-generated custom evaluation dataset): generation, sampling, publish workflow baseline.
- Feature 012 (research reproduction kit): five-variant reproduction and export infrastructure.
- Feature 016 (fair outcome scoring): value-alignment semantics, required-claims, interim task_success — v2.0 supersedes the dual-criterion headline bridge for paper-v2.0 only.
- Feature 015 (repro eval validity): stratum reporting and low-n indicators remain compatible with v2.0 exports.

## Out of Scope

- Changing MRR, MAP, or nDCG@10 definitions or eligibility rules.
- Introducing new LLM or judge model endpoints beyond existing pinned configs.
- Retroactive re-scoring or manifest updates for paper-v1.0 / v1.2.0 reproductions.
- Replacing the required 10% stratified manual audit with fully automated publish without operator review.
- Expanding beyond the 200-item dev split or adding new system variants in this feature.
