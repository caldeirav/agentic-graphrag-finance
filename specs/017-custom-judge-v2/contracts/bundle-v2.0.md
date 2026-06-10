# Contract: Custom-Judge Bundle v2.0.0 (017)

**Path**: `data/benchmarks/custom-judge/v2.0.0/`  
**Parent**: `1.2.0` (immutable, audit lineage only — no item reuse)

## Required artifacts

| File | Purpose |
|------|---------|
| `manifest.json` | `schema_version: "2.0.0"`, `version: "2.0.0"`, `parent_version: "1.2.0"` |
| `items/dev_pool.jsonl` | Full accepted pool (may exceed 200; source for quota selection) |
| `items/dev.jsonl` | 200 net-new quota-balanced dev items |
| `dev_selection_report.json` | Selection metadata (pool, targets, selected_counts, seed) |
| `CHANGELOG.md` | Thematic lineage notes only (no v1.2.0 item IDs) |
| `feasibility_report.json` | All gates including macro-bindability |
| `scorability_report.json` | answer-GT coverage confirmation |
| `reachability_report.json` | Section reachability for all items |
| `publish_audit.json` | Operator sign-off + 20-item audit sample |
| `corpus/` | Refreshed frozen corpus (Git LFS) |
| `relevance_labels.json` | Regenerated for v2 corpus |

## Item schema (v2.0)

Every accepted item MUST have:

```json
{
  "item_id": "v2-finagentbench-001",
  "answer_type": "comparison_structured",
  "ground_truth": {
    "answer": "Both FY2025 and FY2024 10-K filings discuss ...",
    "required_claims": ["...", "...", "..."],
    "rubric": null
  },
  "expected_bindings": { "accessions": ["...", "..."] },
  "multi_filing_required": true
}
```

**Forbidden**: `ground_truth.answer: null`, v1.2.0 `item_id` values, rubric-only headline routing.

## Publish gates (blocking)

| Gate | Rule |
|------|------|
| `item_count` | exactly 200 accepted dev items in `dev.jsonl` |
| `profile_counts` | matches `profile_quotas` targets (largest-remainder on 200) |
| `answer_gt_coverage` | 200/200 items have non-empty `ground_truth.answer` |
| `required_claims` | narrative + comparison_structured: 2–8 atomic claims |
| `comparison_bindings` | comparison/multi-filing items: ≥2 accessions in corpus |
| `multi_filing_floor` | ≥40 items comparison-tagged or `multi_filing_required` |
| `macro_bindability` | 0 failures across all 200 items |
| `reference_corpus` | all bound accessions in corpus index |
| `section_reachability` | all items reachable in graph |
| `question_binding_year_mismatch` | 0 mismatches |
| `rubric_only_count` | 0 in scorability report |
| `publish_audit` | `publish_audit.json` with operator sign-off + 20 audited item ids |

**Not blocking for v2**: `generation_report.pass_rate` (candidate yield). Retained in `generation_report.json` as an indicative metric for tuning generation; publish gates judge final `items/dev.jsonl` only.

## answer_type rules

| answer_type | Bindings | Claims |
|-------------|----------|--------|
| `numeric` | ≥1 | none |
| `short_label` | ≥1 | none |
| `narrative` | ≥1 | 2–8 |
| `comparison_structured` | ≥2 | ≥3 (per-filing + cross-filing) |

## Registry

Published bundle registers as `custom-judge` adapter version `2.0.0`. v1.2.0 adapter entry retained for paper-v1.0 reproductions.
