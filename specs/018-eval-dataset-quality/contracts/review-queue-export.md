# Contract: Review Queue Export (018)

**Feature**: 018-eval-dataset-quality | **Implements**: FR-001

## Inputs

| Source | Fields used |
|--------|-------------|
| `{bundle}/items/dev.jsonl` | Structural item fields |
| `{repro}/{variant}/results.json` | `item_id`, `ranking_metrics.mrr`, `ranking_metrics.ndcg_at_10`, `judge_verdict.scores.value_alignment` or `outcome_score` |
| `{draft}/annotations.jsonl` | Latest `failure_class` per item (optional) |

## Priority tiers

| Tier | Condition | `priority_score` |
|------|-----------|------------------|
| 1 | `outcome_score == 0` AND (`mrr >= 0.5` OR `ndcg_at_10 >= 0.3`) | `max(mrr, ndcg_at_10)` |
| 2 | `outcome_score == 0` AND NOT tier 1 | `0.1` |
| 3 | `outcome_score > 0` | `0.0` |

Sort: tier ASC, `priority_score` DESC, `item_id` ASC.

## CSV columns

```text
item_id,priority_tier,priority_score,mrr,ndcg_at_10,outcome_score,inspiration_profile,
question_preview,latest_failure_class
```

## JSON envelope

```json
{
  "exported_at": "2026-06-20T...",
  "bundle_version": "2.0.0",
  "repro_input": "reports/repro-paper-v1.0",
  "baseline_variant": "graph-full",
  "tier_counts": {"1": 45, "2": 48, "3": 107},
  "entries": [ "...ReviewQueueEntry..." ]
}
```

## Filter flags (CLI)

| Flag | Effect |
|------|--------|
| `--tier 1` | Export subset |
| `--exclude-annotated agent_failure` | Omit agent_failure from worklist |
| `--max-items N` | Cap export size |

## Missing repro

When `--repro-input` omitted: all items tier 3, `priority_score=0`, repro columns empty.
