# Contract: Judge v3 Resume & Completeness (016)

**Consumers**: `judge-batch`, checkpoint persistence  
**Producers**: `gemini_panel.py`, `judge_batch.py`

## Version stamp

Every new verdict MUST include:

```json
{
  "judge_version": "v3",
  "scores": { "<criterion_id>": 0.0 },
  "criteria": ["<criterion_id>", ...]
}
```

## Skip predicate

```python
def should_skip_judging(
    existing: JudgeVerdict | None,
    item: BenchmarkItem,
    variant_id: str,
    force_rescore: bool,
) -> bool:
    if force_rescore or existing is None:
        return False
    if parse_version(existing.judge_version) < 3:
        return False
    required = set(criteria_for_item(item, variant_id=variant_id))
    return required <= set(existing.scores.keys())
```

## CLI behavior

| Flag | Effect |
|------|--------|
| (default) | Skip only v3-complete verdicts |
| `--force-rescore` | Re-judge all items |

## Backward compatibility

- v1/v2 checkpoints: always re-judged
- No automatic migration of stored scores; re-judge produces v3
