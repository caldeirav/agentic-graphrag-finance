# Data Model: Custom-Judge Bundle v2.0 (017)

**Feature**: 017-custom-judge-v2 | **Date**: 2026-06-02

## Entity relationship overview

```text
GeneratedBenchmarkItem (v2.0)
    ├── answer_type                     ──► publish gate + judge prompt shape
    ├── ground_truth.answer (required)  ──► value_alignment target
    ├── ground_truth.required_claims[]  ──► graded VA (non-numeric / comparison)
    ├── ground_truth.rubric (optional)  ──► auxiliary judge hint only
    ├── expected_bindings               ──► macro + corpus gates
    ├── multi_filing_required           ──► floor count (≥40 across split)
    └── question_type_tag               ──► comparison detection

DevItemPool (v2.0 draft/publish)
    └── items/dev_pool.jsonl          ──► all unique accepted items (≥200)

DevSelectionReport (v2.0)
    ├── pool_count
    ├── selected_count (200)
    ├── targets{profile → int}
    ├── selected_counts{profile → int}
    └── seed

BundleManifest (v2.0.0)
    ├── schema_version: "2.0.0"
    ├── parent_version: "1.2.0"
    ├── item_count: 200
    ├── profile_counts{profile → int}
    ├── items_hash, corpus hashes
    └── publish_audit_path

PublishAuditRecord
    ├── operator_signoff_at
    ├── feasibility_report_hash
    ├── scorability_report_hash
    └── manual_audit_item_ids[20]

paper-v2.0 ReleaseManifest
    ├── custom_judge_version: "2.0.0"
    ├── corpus_hashes, relevance_labels_hash
    └── full_reproduction_required: true

task_success (v2.0 export)
    └── mean(value_alignment) over n=200 eligible items
```

## AnswerType (new enum)

| Value | Description | required_claims |
|-------|-------------|-----------------|
| `numeric` | Percentage, currency, integer | omitted |
| `short_label` | ≤4 tokens, canonical label | omitted |
| `narrative` | Prose answer | 2–8 claims |
| `comparison_structured` | Both-filings template answer | ≥3 claims (per-filing + semantic cross-filing synthesis) |

## GroundTruth (v2.0 constraints)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `answer` | string | **Yes** | Non-null, non-empty for all v2 items |
| `required_claims` | list[string] | Conditional | Required for `narrative` and `comparison_structured` |
| `rubric` | string \| null | No | Auxiliary only; not headline GT |
| `relevant_chunk_ids` | list[string] | No | Unchanged |

## GeneratedBenchmarkItem (extensions)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `answer_type` | AnswerType | Yes (v2) | Drives validation and generation prompts |
| `item_id` | string | Yes | Net-new IDs; no v1.2.0 IDs |
| `multi_filing_required` | bool | Conditional | True for comparison floor counting |
| `inspiration_profile` | enum | Yes | financebench / finder / finagentbench |

## ComparisonStructuredAnswer (logical shape)

| Component | Example |
|-----------|---------|
| `filing_a_label` | FY2025 10-K |
| `filing_b_label` | FY2024 10-K |
| `topic` | supply chain risk |
| `section_a` | Item 7 MD&A |
| `section_b` | Item 7 MD&A |
| `canonical_answer` | Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A. |

## FeasibilityReport (v2.0 extensions)

| Field | Type | Notes |
|-------|------|-------|
| `blocked_items[]` | list | `{item_id, reason, detail}` |
| `macro_bindability_failures` | int | Must be 0 at publish |
| `multi_filing_count` | int | Must be ≥40 at publish |
| `answer_gt_coverage` | float | Must be 1.0 at publish |

**Blocking reason codes** (v2-only additions):

| Code | Rule |
|------|------|
| `missing_answer_gt` | `ground_truth.answer` empty |
| `macro_bindability` | macro validator failed |
| `multi_filing_floor` | split has <40 multi-filing items |
| `invalid_answer_type` | comparison item without `comparison_structured` |
| `comparison_bindings` | <2 accessions (unchanged from v1.x) |
| `required_claims` | narrative/comparison missing valid claims |
| `section_reachability` | path not in graph (unchanged) |

## ScorabilityReport

| Field | Type | Notes |
|-------|------|-------|
| `scorable_item_count` | int | Must equal 200 |
| `by_answer_type` | dict | Counts per AnswerType |
| `rubric_only_count` | int | Must be 0 |

## PublishAuditRecord

| Field | Type | Notes |
|-------|------|-------|
| `audit_sample_size` | int | 20 |
| `audit_sample_item_ids` | list[string] | Stratified by profile + answer_type |
| `operator_id` | string | From env or CLI flag |
| `signed_off_at` | datetime | Required before publish |

## task_success v2.0 (export row)

| Field | Value |
|-------|-------|
| `metric_name` | `task_success` |
| `item_count` | 200 |
| `value` | mean(`outcome_score`) where outcome = VA |
| `na_reason` | never `rubric_only` for v2 bundles |

## State transitions

```text
draft → validated → audit_pending → published
         ↑              ↑
    feasibility      operator sign-off
    gates pass       + 20-item audit
```

Publish blocked unless: quota-balanced `dev.jsonl` (200 items), all feasibility gates pass, scorability report clean, `publish_audit.json` present with sign-off.

**Not blocking for v2**: `generation_report.pass_rate` (candidate pool yield; indicative for tuning generation).
