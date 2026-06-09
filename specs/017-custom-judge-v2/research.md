# Research: Custom-Judge Bundle v2.0 (017)

**Feature**: 017-custom-judge-v2 | **Date**: 2026-06-02

## R1 — Net-new vs migrate authoring path

**Decision**: Greenfield generation only; no `migrate_v1_2_0.py`-style in-place item carryover.

**Rationale**: Clarification session locked net-new pool (no v1.2.0 questions, bindings, or IDs). v1.x migrations preserved infeasible bindings and rubric-only routing that v2.0 explicitly retires.

**Alternatives considered**:
- *Heavy migrate subset* — rejected; conflicts with FR-006 and audit clarity.
- *Questions-only reuse* — rejected; same conflict.

## R2 — Refreshed corpus sampling

**Decision**: New generation config `custom_judge_v2.yaml` with new `random_seed`, filing window `min_fiscal_year: 2023` / `max_fiscal_year: 2026`, same 20-issuer allowlist governance as v1.

**Rationale**: Spec requires distinct `corpus_hashes` from paper-v1.0/v1.2.0 while keeping third-party reproducibility via allowlist + seed. Shifting the fiscal window yields fresh accessions without unbounded SEC crawling.

**Alternatives considered**:
- *Reuse v1.2.0 corpus, new items only* — rejected in clarify (refreshed corpus).
- *Expand issuer count* — deferred; increases materialization cost; can follow on if feasibility fails.

## R3 — Comparison ground-truth shape

**Decision**: `answer_type: comparison_structured` with canonical template:

> Both {filing_a_label} and {filing_b_label} discuss {topic} in {section_a} / {section_b}.

Required claims: one per filing attribution + one cross-filing comparison claim (minimum 3, maximum 8 total).

**Rationale**: Clarification chose structured answer + atomic claims for partial credit via value_alignment (judge v3.1 graded VA), not rubric-only claim_presence.

**Alternatives considered**:
- *Boolean only, no claims* — rejected; loses partial credit when one filing supports topic.
- *Free-form rubric* — rejected; not unified task_success path.

## R4 — Macro-bindability publish gate

**Decision**: Blocking gate for **all 200 items** using `validate_macro_binding()` against each item's `expected_bindings` and question text on the bundled composite snapshot.

**Rationale**: Clarification session; prevents reproduction macro failures that v1.x discovered post hoc.

**Alternatives considered**:
- *Comparison-only gate* — rejected by operator choice.
- *Advisory report* — rejected; insufficient for paper lock credibility.

## R5 — task_success aggregation for paper-v2.0

**Decision**: `task_success = mean(outcome_score)` over all headline-eligible items where `outcome_score` derives solely from `value_alignment`; missing VA = 0; n=200. Do not fall back to `claim_presence` for any item.

**Rationale**: 016 `task_success` bridged VA + rubric for v1.x dual GT shapes. v2.0 has 100% answer-GT, so bridge is unnecessary and misleading.

**Alternatives considered**:
- *Keep dual-criterion bridge* — rejected; contradicts FR-009/FR-012.
- *Rename metric* — rejected; keep `task_success` as headline with updated definition under paper-v2.0 lock.

## R6 — Report treatment of rubric_alignment

**Decision**: Omit `rubric_alignment` rows entirely from paper-v2.0 exports and HTML report headline tables.

**Rationale**: Clarification session; prevents v1.x mental model confusion.

**Alternatives considered**:
- *Diagnostic appendix* — rejected by operator.
- *Show with disclaimer* — rejected.

## R7 — Operator publish audit

**Decision**: Automated gates + operator sign-off on feasibility/scorability reports + **10% stratified manual review (20 items)** recorded in `publish_audit.json`.

**Rationale**: Clarification session balances quality with operator time; stratified sample covers profiles and answer types.

**Alternatives considered**:
- *Reports only* — rejected.
- *Full 200 review* — rejected as impractical for initial v2.0 ship.

## R8 — Multi-filing floor

**Decision**: Minimum **40** accepted items tagged comparison or `multi_filing_required: true`; blocking publish gate.

**Rationale**: Clarification session (20% of dev split); FinAgentBench-style coverage for agentic retrieval claims.

## R9 — Judge version for v2 evaluation

**Decision**: Reuse judge **v3.1** value_alignment + required_claims policy; no new model endpoint. Bundle manifest records `evaluation_judge_version` and config hash; paper-v2.0 manifest pins same.

**Rationale**: Spec out of scope for new endpoints; v3.1 already supports graded VA with claims.

## R10 — Item identity and lineage

**Decision**: v2.0 item IDs are newly minted (`v2-{profile}-{seq}` or UUID slug); CHANGELOG may note thematic lineage to v1.2.0 intents without reusing IDs.

**Rationale**: Net-new pool clarification; simplifies repro artifact isolation.
