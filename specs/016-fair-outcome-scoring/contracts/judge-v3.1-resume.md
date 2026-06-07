# Contract: Judge v3.1 Resume & Graded VA (016)

**Consumers**: `judge-batch`, checkpoint persistence  
**Producers**: `gemini_panel.py`, `judge_batch.py`

## Version stamp

Every new verdict MUST include:

```json
{
  "judge_version": "v3.1",
  "scores": { "<criterion_id>": 0.0 },
  "criteria": ["<criterion_id>", ...]
}
```

`value_alignment` uses graded rubric semantics (partial credit for claims and numeric tolerance).

## Skip predicate

```python
MIN_JUDGE_VERSION = 3.1

def should_skip_judging(existing, item, variant_id, force_rescore) -> bool:
    if force_rescore or existing is None:
        return False
    if parse_version(existing.judge_version) < MIN_JUDGE_VERSION:
        return False
    required = set(criteria_for_item(item, variant_id=variant_id))
    return required <= set(existing.scores.keys())
```

## CLI behavior

| Flag | Effect |
|------|--------|
| (default) | Skip only v3.1+-complete verdicts |
| `--force-rescore` | Re-judge all items |

## Backward compatibility

- v1/v2/v3 checkpoints: always re-judged (version < 3.1)
- Export manifest `min_judge_version`: `v3.1`
