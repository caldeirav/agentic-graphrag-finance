# Data Model: Evaluation Dataset Quality (018)

**Feature**: 018-eval-dataset-quality | **Date**: 2026-06-20

## FailureClass

```text
gt_too_strict | gt_wrong | gt_boilerplate | question_ambiguous |
claims_misaligned | acceptable_hard | agent_failure
```

Single primary class per annotation record.

## ItemAnnotation

Append-only row in `annotations.jsonl`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `annotation_id` | string (uuid) | yes | Unique per record |
| `item_id` | string | yes | Dev split item |
| `reviewer_id` | string | yes | Operator identity |
| `created_at` | datetime (UTC ISO) | yes | |
| `failure_class` | FailureClass | yes | One primary class |
| `notes` | string | no | Free text; nuance for multi-factor cases |
| `corpus_spot_check` | enum | yes | `pending` \| `passed` \| `failed` |
| `proposed_overrides` | object | no | Partial item patch (see ProposedOverrides) |
| `repro_context` | object | no | Snapshot of MRR, nDCG, outcome_score at review time |

## ProposedOverrides

Optional nested object on annotation; applied only via `apply-overrides`.

| Field | Type | Notes |
|-------|------|-------|
| `question` | string | |
| `ground_truth.answer` | string | |
| `ground_truth.required_claims` | string[] | |
| `expected_section_paths` | string[] | |
| `expected_bindings` | ExpectedBindings | Same schema as GeneratedBenchmarkItem |

## OverrideChangelogEntry

Row in `override_changelog.jsonl` after successful apply.

| Field | Type | Required |
|-------|------|----------|
| `item_id` | string | yes |
| `parent_item_hash` | string (sha256) | yes |
| `applied_at` | datetime | yes |
| `reviewer_id` | string | yes |
| `annotation_id` | string | yes |
| `changed_fields` | string[] | yes |
| `rationale` | string | no |
| `validation_outcome` | enum | yes | `accepted` \| `rejected` |
| `validation_errors` | string[] | when rejected |

## ReviewQueueEntry

Exported row in `review_queue.json` / CSV.

| Field | Type | Required |
|-------|------|----------|
| `item_id` | string | yes |
| `priority_tier` | int | yes | 1=highest (dataset-likelihood) |
| `priority_score` | float | yes | Sort key within tier |
| `mrr` | float | no | From graph-full repro |
| `ndcg_at_10` | float | no | |
| `outcome_score` | float | no | value_alignment |
| `inspiration_profile` | string | yes | |
| `question_preview` | string | yes | First 120 chars |
| `latest_annotation_class` | FailureClass | no | If annotated |

### Priority rules

1. Tier 1: `outcome_score == 0` AND (`mrr >= 0.5` OR `ndcg_at_10 >= 0.3`)
2. Tier 2: `outcome_score == 0` AND NOT tier 1
3. Tier 3: `outcome_score > 0` AND structural/anomaly flags (optional export filter)

Within tier: sort by `max(mrr, ndcg_at_10)` descending, then `item_id`.

## DuplicateRejectionFeedback

Row in `duplicate_feedback.jsonl` (generation phase).

| Field | Type | Required |
|-------|------|----------|
| `rejected_question` | string | yes |
| `matched_item_id` | string | yes | Prior accept or candidate |
| `inspiration_profile` | string | yes |
| `issuer_ticker` | string | yes |
| `similarity_score` | float | yes |
| `rejected_at` | datetime | yes |

## DiversityGovernanceConfig

Extension to `GenerationConfig.governance`.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `max_items_per_issuer_per_profile` | int | 8 | Cap per profile during generation |
| `min_unique_question_type_tags_per_profile` | int | 6 | Floor before publish warning |
| `prompt_negative_examples_count` | int | 5 | Prior questions injected per Gemini call |
| `duplicate_feedback_enabled` | bool | true | Write duplicate_feedback.jsonl |

## DiversityReport

`diversity_report.json` in draft bundle.

| Field | Type |
|-------|------|
| `duplicate_rejection_rate` | float |
| `duplicate_rejection_count` | int |
| `candidates_total` | int |
| `by_profile` | dict[profile, ProfileDiversityStats] |
| `baseline_reference` | string | e.g. `v2.0.0` |

### ProfileDiversityStats

| Field | Type |
|-------|------|
| `unique_issuers` | int |
| `unique_question_type_tags` | int |
| `items_accepted` | int |

## QualityPassSummary

`quality_pass_summary.json` after review pass + selective re-judge.

| Field | Type |
|-------|------|
| `items_reviewed` | int |
| `items_fixed_override` | int |
| `items_fixed_regenerate` | int |
| `failure_class_counts` | dict[FailureClass, int] |
| `dataset_caused_zero_score_count` | int |
| `dataset_caused_zero_score_rate` | float |
| `rejudge_improved_count` | int |
| `rejudge_improved_rate` | float |

## Draft bundle layout (extensions)

```text
drafts/{run_id}/
├── annotations.jsonl              # NEW: append-only review records
├── override_changelog.jsonl       # NEW: applied overrides audit
├── duplicate_feedback.jsonl       # NEW: generation duplicate captures
├── diversity_report.json          # NEW: post-generation diversity metrics
├── review_queue.json              # NEW: exported queue (optional)
├── review_pack.html               # NEW: human audit pack
├── review_pack.csv                # NEW: annotation import companion
├── quality_pass_summary.json      # NEW: post re-judge summary
└── items/dev.jsonl                # UPDATED only via apply-overrides / regenerate-item
```

## State transitions

```text
Item (dev.jsonl)
  → annotated (annotations.jsonl append)
  → proposed (proposed_overrides on annotation)
  → applied (override_changelog + dev.jsonl patch)
  → validated (v2 gates re-run)
  → published (v2.0.1 manifest)

Annotation corpus_spot_check: pending → passed | failed
```

## Validation additions (v2.0.1)

| Error code | Trigger |
|------------|---------|
| `boilerplate_comparison_answer` | comparison_structured + `is_boilerplate_comparison_answer` |
| `borderline_comparison_answer` | passes auto gate but flagged in scorability report for human audit |
