# Contract: Annotations Sidecar (018)

**Path**: `{draft_root}/annotations.jsonl`

## Format

- JSONL, one `ItemAnnotation` per line (see [data-model.md](../data-model.md))
- Append-only: new records MUST NOT delete or rewrite prior lines
- UTF-8, sorted by `created_at` on export only (storage order = append order)

## Example record

```json
{
  "annotation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "item_id": "v2-finagentbench-0022",
  "reviewer_id": "vincent",
  "created_at": "2026-06-20T14:30:00Z",
  "failure_class": "gt_boilerplate",
  "notes": "Canonical answer only states both discuss Item 1A",
  "corpus_spot_check": "passed",
  "proposed_overrides": {
    "ground_truth": {
      "answer": "Caterpillar emphasizes cyclical end-market demand while Exxon Mobil emphasizes commodity price volatility in their 2025 10-K risk disclosures.",
      "required_claims": ["..."]
    }
  },
  "repro_context": {
    "mrr": 0.75,
    "ndcg_at_10": 0.62,
    "outcome_score": 0.0
  }
}
```

## Apply eligibility

An annotation is **eligible for apply** when:
1. `corpus_spot_check == "passed"`
2. `proposed_overrides` is non-empty
3. `failure_class != "agent_failure"` (unless `--force` on apply)
4. No newer annotation for same `item_id` with `corpus_spot_check == "failed"`

## Published bundle

`annotations.jsonl` and `override_changelog.jsonl` MAY be copied to published v2.0.1 for audit; not used at eval runtime (eval reads `items/dev.jsonl` only).
