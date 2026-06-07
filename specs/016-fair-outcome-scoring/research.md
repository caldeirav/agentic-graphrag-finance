# Research: Fair Reproduction Outcome Scoring (016)

**Feature**: 016-fair-outcome-scoring | **Date**: 2026-06-07

## R1 — Outcome score mapping (no synthesis fallback)

**Decision**: For items with `ground_truth.answer`, `outcome_score = value_alignment` when present; when `value_alignment` is absent from the judge verdict, `outcome_score = 0.0` (item remains in outcome_accuracy denominator).

**Rationale**: paper-v1.0 analysis showed 91/91 HTML answer-GT items missing `value_alignment` with synthesis_grounding used as fallback; flat-chunk chunk-dumps scored synthesis=1.0 while graph-full honest partial answers scored 0. Clarification session chose visible zero over exclusion.

**Alternatives considered**:
- Exclude missing-VA items from denominator — rejected: hides incomplete judge coverage.
- Fallback to synthesis when VA missing — rejected: root cause of flat-chunk inflation.

---

## R2 — Judge version v3 and resume gate

**Decision**: `GeminiJudgePanel` emits `judge_version="v3"`. Resume skip requires version ≥ 3 **and** stored verdict includes every criterion from `criteria_for_item(item, variant_id=...)`. All v2 verdicts are re-judged on next batch.

**Rationale**: v2 resume gate (015) preserved incomplete 4-criterion verdicts as "done". Version bump gives operators a clear migration boundary and simplifies skip logic vs parsing partial criterion history.

**Alternatives considered**:
- Criterion completeness only on v2 — rejected: harder to audit which checkpoints are pre-fix.
- Bump only on force-rescore — rejected: normal batch would still skip stale v2.

---

## R3 — Variant-aware judge criteria

**Decision**:
- **Graph variants** (`graph-full`, ablations): existing trajectory set + GT-aware criteria (`value_alignment`, `claim_presence` when applicable).
- **flat-chunk**: `retrieval_fidelity`, `answer_quality`, `synthesis_grounding` (anti-chunk-dump), plus `value_alignment` / `claim_presence` per GT type. Exclude `trajectory_coherence`, `routing_decisions`, `trajectory_fidelity`.

**Rationale**: flat-chunk has no macro/meso/micro trajectory; judging it on routing incoherence is meaningless. `answer_quality` scores whether the response addresses the question using retrieved evidence substantively.

**Alternatives considered**:
- Same criteria for all variants — rejected: unfair to flat-chunk and dilutes graph trajectory signal.
- Change flat-chunk answer synthesis to LLM summary — rejected: out of scope; judge rubric path fixes gaming without re-running agents.

---

## R4 — Judge rubric anti-gaming

**Decision**: Extend `configs/judges/gemini_2_5_pro.yaml` and prompt builder:
- `synthesis_grounding`: score 0 for verbatim chunk concatenation without answering the question; 0 for wrong-issuer/filing citations vs `expected_bindings`.
- `value_alignment`: qualitative GT scored by claim coverage; include `required_claims` in prompt when present; penalize header/fragment overlap without substance.
- `answer_quality` (new): 0–1 whether answer addresses question using cited evidence (flat-chunk primary outcome signal besides VA).

**Rationale**: Matches observed failure mode: `Based on retrieved chunks:\n{excerpt}...` passes old synthesis rubric.

**Alternatives considered**:
- Post-process flat-chunk answers to detect dump pattern in code — rejected: judge remains source of truth for paper metrics.
- Numeric-only value_alignment — rejected: FinAgentBench narrative items need claim coverage.

---

## R5 — Bundle v1.1.0 (not in-place v1.0.0 edit)

**Decision**: Publish new immutable bundle `data/benchmarks/custom-judge/v1.1.0/` with `CHANGELOG.md` listing item-level changes vs v1.0.0. Update `releases/paper-v1.0/manifest.yaml` `custom_judge_bundle_path` and `custom_judge_version` to `1.1.0`.

**Rationale**: Clarification session chose new version for audit trail; v1.0.0 remains reproducible baseline.

**Alternatives considered**:
- In-place migration of v1.0.0 — rejected: breaks immutability of published artifacts.
- Full dev-split regeneration — rejected: selective migration + changelog sufficient.

---

## R6 — Required-claims on non-numeric answer-GT

**Decision**: Attach `ground_truth.required_claims: list[str]` to all answer-GT items classified as non-numeric via `is_numeric_answer_gt(answer: str) -> bool` heuristic (percentage, currency, plain number, short label ≤ 4 tokens without narrative verbs). Narrative items get 3–8 atomic claims derived at migration from existing answer text + rubric.

**Rationale**: Clarification: non-numeric answer-GT items need machine-checkable structure; FinanceBench numeric items stay single-target VA.

**Alternatives considered**:
- Length threshold (>120 chars) — rejected in clarification in favor of numeric vs narrative split.
- Required-claims on all answer-GT — rejected: over-structures numeric answers.

---

## R7 — Rubric-only routing for comparison/reference types

**Decision**: For `question_type_tag` in `{cross-filing-comparison, multi-hop-narrative, reference-following}` (and existing tags matching those patterns), set `ground_truth.answer = null` and populate `ground_truth.rubric` with claim checklist; outcome_accuracy excludes item; rubric_alignment includes it.

**Rationale**: Long comparison GT strings are not value-alignment targets; claim_presence is the correct metric.

**Alternatives considered**:
- Keep answer GT + required_claims — rejected: duplicates rubric and confuses outcome vs alignment aggregates.

---

## R8 — Corpus feasibility validation at publish

**Decision**: Extend `check_publish_gates()` with:
- Comparison items: ≥2 distinct accessions in `expected_bindings` when tag implies comparison.
- Reference-following: referenced accession in bindings appears in bundle corpus index.
- Emit blocking errors in publish report; `skip_gates` only for dev fixtures.

**Rationale**: Macro binding failures (`missing_comparison_partner`) produced high outcome with zero citations in paper-v1.0.

**Alternatives considered**:
- Warn-only — rejected: SC-006 requires zero infeasible comparison items at publish.

---

## R9 — Selective operator re-run

**Decision**: `CHANGELOG.md` lists `item_id`, change type (`question`, `bindings`, `ground_truth`, `rubric_route`). Docs prescribe: unchanged items → `judge-batch --force-rescore` + export; changed items → `repro run --variants ... --resume` for affected variants only (or single-item filter when implemented).

**Rationale**: Clarification session; avoids full 1000-query reproduction.

**Alternatives considered**:
- Full repro mandatory — rejected: operator cost.
- Re-judge only for all — rejected: stale agent answers on revised questions.

---

## R10 — SC-001 failure escalation

**Decision**: `aggregate_investigation_notes` emits `OUTCOME_ORDERING_REGRESSION` when graph-full outcome ≤ flat-chunk on HTML stratum or pooled headline after v3 re-score; severity `warning`; includes deltas and 5 example item ids. Does not block feature merge.

**Rationale**: Clarification: ship scoring fixes even if comparative outcome ordering fails; surface for follow-up.

**Alternatives considered**:
- Hard CI gate — rejected in clarification.

---

## R11 — Report prominence for stratified outcome

**Decision**: HTML report adds dedicated "Outcome by profile" and "Outcome by evidence source" sections above pooled headline table (not buried in raw CSV appendix). Export manifest records `bundle_version` and `judge_version_min`.

**Rationale**: FR-010; 015 already exports CSVs but operators missed stratum inversion.

**Alternatives considered**:
- CSV-only — rejected: spec requires report visibility.
