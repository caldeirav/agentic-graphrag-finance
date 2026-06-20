# Contract: Diversity Governance (018)

**Feature**: 018-eval-dataset-quality | **Config**: `configs/benchmarks/generation_config_schema` extension

## Config fields

Add to `governance` block in `custom_judge_v2.yaml` (and quality extend configs):

```yaml
governance:
  dedup_similarity_threshold: 0.85
  duplicate_feedback_enabled: true
  max_items_per_issuer_per_profile: 8
  min_unique_question_type_tags_per_profile: 6
  prompt_negative_examples_count: 5
```

## Generation behavior

1. **Issuer cap**: Before scheduling Gemini call, skip issuer if profile already has `max_items_per_issuer_per_profile` accepts.
2. **Negative examples**: Inject `prompt_negative_examples_count` recent accepted questions (same profile, different issuer) into Gemini prompt as "do not repeat".
3. **Duplicate feedback**: On duplicate rejection, append `duplicate_feedback.jsonl` row (see data-model).

## Diversity report

Written to draft root after judge phase completes.

### Baseline comparison (SC-004)

Compare against v2.0.0 `generation_report.json`:
- `duplicate_rejection_rate` = `duplicate_question_count / candidates_total`
- Target: ≥10pp reduction vs ~0.40 baseline

### Publish advisory

Warn (non-blocking) if `unique_question_type_tags < min_unique_question_type_tags_per_profile` for any profile in final dev split.

## Operator feedback loop

```bash
# Aggregate duplicate patterns for prompt edit
jq -s 'group_by(.issuer_ticker) | map({issuer: .[0].issuer_ticker, count: length})' \
  data/benchmarks/custom-judge/drafts/quality-v2.0.1/duplicate_feedback.jsonl
```

Manual edit `configs/benchmarks/inspiration_profiles/*.yaml` → re-run `regenerate-item` or targeted judge slots.
