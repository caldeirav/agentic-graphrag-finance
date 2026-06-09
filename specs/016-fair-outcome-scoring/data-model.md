# Data Model: Fair Reproduction Outcome Scoring (016)

**Feature**: 016-fair-outcome-scoring | **Date**: 2026-06-07

## Entity relationship overview

```text
BenchmarkItem (v1.1.0)
    ├── ground_truth.answer?          ──► outcome_accuracy (value_alignment only)
    ├── ground_truth.rubric?          ──► rubric_alignment (claim_presence only)
    ├── ground_truth.required_claims[] ──► judge prompt + value_alignment (non-numeric answer-GT)
    ├── question_type_tag             ──► rubric-only routing rules
    └── expected_bindings             ──► feasibility validation

JudgeVerdict (v3)
    ├── judge_version: "v3"
    ├── scores: criterion_id → float
    └── criteria[]                    ──► resume completeness check

VariantJudgeProfile
    ├── variant_id
    └── required_criterion_ids[]      ──► flat-chunk vs graph sets

BundleChangelogEntry
    ├── item_id
    ├── change_types[]
    └── notes

BenchmarkResult (unchanged storage)
    ├── outcome_score                 ──► derived from VA only (answer-GT)
    └── alignment_score             ──► derived from claim_presence only (rubric-GT)
```

## GroundTruth (extended)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `answer` | string \| null | No | Null when rubric-only routed |
| `rubric` | string \| null | No | Required for rubric-only items |
| `required_claims` | list[string] | Conditional | Required when answer present and non-numeric |
| `relevant_chunk_ids` | list[string] | No | Unchanged from 011 |

**Numeric answer classification** (`is_numeric_answer_gt`):

| Pattern | Example | required_claims |
|---------|---------|-----------------|
| Percentage | `20.69%` | omitted |
| Currency/number | `$1.2B`, `42` | omitted |
| Short label (≤4 tokens, no verbs) | `GBS`, `Upstream` | omitted |
| Narrative (default) | multi-sentence prose | required (3–8 claims) |

## JudgeCriterionSet

| Variant class | Criteria |
|---------------|----------|
| graph | trajectory_coherence, routing_decisions, retrieval_fidelity, synthesis_grounding, value_alignment?, claim_presence? |
| flat-chunk | retrieval_fidelity, answer_quality, synthesis_grounding, value_alignment?, claim_presence? |

`?` = included when item ground truth requires it.

## ResumeSkipState

An item is **resumable** (skip judging) when:

1. `judge_verdict.judge_version` parses to ≥ 3
2. `set(verdict.scores.keys()) ⊇ criteria_for_item(item, variant_id)`
3. `--force-rescore` not set

## InvestigationNote (extended pattern codes)

| pattern_code | Severity | Trigger |
|--------------|----------|---------|
| `INCOMPLETE_JUDGE_CRITERIA` | warning | answer-GT item lacks value_alignment after complete batch |
| `OUTCOME_ORDERING_REGRESSION` | warning | SC-001 not met post v3 re-score |
| `RUBRIC_ALIGNMENT_ZERO` | warning | unchanged from 014; should not fire after v3 |

## BundlePublishManifest (v1.1.0)

| Field | Type | Notes |
|-------|------|-------|
| `version` | string | `1.1.0` |
| `parent_version` | string | `1.0.0` |
| `changelog_path` | string | `CHANGELOG.md` relative to bundle root |
| `feasibility_report` | object | counts of blocked/warned items at publish |

## ExportManifest (extended)

| Field | Type | Notes |
|-------|------|-------|
| `custom_judge_version` | string | `1.1.0` |
| `min_judge_version` | string | `v3` |
| `outcome_scoring_policy` | string | `value_alignment_only` |

## Report sections (HTML)

| Section id | Source table | Primary metrics |
|------------|--------------|-----------------|
| `outcome-by-profile` | `by_profile.csv` | outcome_accuracy per inspiration_profile |
| `outcome-by-stratum` | `by_evidence_source.csv` | outcome_accuracy per primary_evidence_source |
| `headline-pooled` | `headline.csv` | existing pooled view |
