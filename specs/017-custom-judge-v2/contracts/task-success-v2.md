# Contract: task_success v2.0 (017)

**Scope**: paper-v2.0 reproduction exports and HTML reports only. v1.x reproductions retain 016 semantics.

## Definition

```
task_success = (1/n) * Σ value_alignment_i
```

Where:
- `n` = count of headline-eligible dev items (200 for full split)
- `value_alignment_i` = stored judge `outcome_score` (= VA criterion) for item `i`
- Missing or absent `value_alignment` → contributes **0.0** (item stays in denominator)

## Eligibility

| Rule | v2.0 behavior |
|------|---------------|
| Headline eligible | Same as 015 (`_headline_eligible`) |
| Answer-GT required | All v2 items have answer GT by publish gate |
| Rubric-only exclusion | **Removed** — no items excluded for rubric-only |
| claim_presence | **Not used** for task_success on v2 bundles |

## Export rows

Headline CSV/JSON export MUST include:

| metric_name | item_count | notes |
|-------------|------------|-------|
| `task_success` | 200 | sole headline outcome metric |
| `ndcg_at_10` | ≤200 | unchanged definition |
| `trajectory_fidelity` | 200 | unchanged definition |

Headline export MUST **NOT** include:

| metric_name | Reason |
|-------------|--------|
| `rubric_alignment` | No rubric-only GT in v2.0 |
| `outcome_accuracy` | Optional diagnostic only; if present, equals task_success for v2 |

## Bundle version detection

When release manifest `custom_judge_version >= "2.0.0"` (semver compare):

- `_task_success_score()` returns `outcome_score` for every eligible item with answer GT
- `_aggregate_metrics()` sets `rubric_alignment` to `None` and omits from export row list
- Report renderer skips rubric_alignment section

## Stratum tables

Profile and evidence-stratum breakdowns use **task_success** (VA-derived) with full n per stratum where eligible; no `na_reason=rubric_only`.

## Tests

- Fixture: 200 items all with VA scores → task_success = mean(VA)
- Fixture: 5 items missing VA → those contribute 0; n still 200
- Fixture: paper-v1.0 manifest → rubric_alignment row still exported (backward compat)
