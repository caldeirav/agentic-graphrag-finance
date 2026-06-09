# Contract: Outcome Scoring Policy (016)

**Consumers**: `export-tables`, `report`, headline CSV, investigation notes  
**Producer**: `src/evaluation/judges/outcome_scoring.py`

## Rules

### Answer-ground-truth items

```
IF ground_truth.answer IS NOT NULL:
    IF value_alignment IN judge_verdict.scores:
        outcome_score = judge_verdict.scores["value_alignment"]
    ELSE:
        outcome_score = 0.0
    # NEVER use synthesis_grounding for outcome_score
```

Item **included** in `outcome_accuracy` denominator regardless of missing VA.

### Rubric-ground-truth items

```
IF ground_truth.rubric IS NOT NULL AND ground_truth.answer IS NULL:
    outcome_score = NULL  # excluded from outcome_accuracy
    alignment_score = claim_presence OR 0.0 if missing
```

### Abstention

When agent abstains and answer GT exists: `outcome_score = 0.0` (unchanged from 015).

## Composite headline fields

| Export column | Definition |
|---------------|------------|
| `outcome_accuracy` | mean(outcome_score) over answer-GT eligible items |
| `rubric_alignment` | mean(alignment_score) over rubric-GT eligible items |

## Investigation note trigger

Emit `INCOMPLETE_JUDGE_CRITERIA` when any answer-GT item in variant run has `value_alignment` absent after judge batch marked complete.
