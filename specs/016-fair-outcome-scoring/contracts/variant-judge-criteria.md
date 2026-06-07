# Contract: Variant-Aware Judge Criteria (016)

**Producer**: `criteria_for_item(item, variant_id)` in `outcome_scoring.py`  
**Consumer**: `gemini_panel.py` prompt assembly

## Criterion catalog

| id | Applies to | Description |
|----|------------|-------------|
| `trajectory_coherence` | graph variants | Macro/meso/micro path consistency |
| `routing_decisions` | graph variants | Tool routing vs expected trajectory |
| `retrieval_fidelity` | all | Retrieved chunks match relevant evidence |
| `synthesis_grounding` | all | Answer grounded in retrieved evidence; anti-chunk-dump |
| `answer_quality` | flat-chunk | Substantive answer vs question (not dump) |
| `value_alignment` | answer-GT | Numeric or claim-based answer correctness |
| `claim_presence` | rubric-GT | Rubric checklist coverage |

## Variant sets

```python
GRAPH_VARIANTS = {
    "graph-full",
    "ablation-no-macro",
    "ablation-no-walker",
    "ablation-xbrl-only",
    "ablation-no-xbrl",
}
FLAT_VARIANT = "flat-chunk"

def base_criteria(variant_id: str) -> list[str]:
    if variant_id == FLAT_VARIANT:
        return ["retrieval_fidelity", "answer_quality", "synthesis_grounding"]
    return [
        "trajectory_coherence",
        "routing_decisions",
        "retrieval_fidelity",
        "synthesis_grounding",
    ]
```

GT extensions appended after base set:

- `value_alignment` if `ground_truth.answer`
- `claim_presence` if `ground_truth.rubric`

## Rubric prompt injection

When `required_claims` non-empty, judge prompt includes:

```
Required claims for value_alignment:
- {claim_1}
- {claim_2}
...
```

## synthesis_grounding rubric (normative)

Score **0.0** when:
- Response is primarily concatenated chunk text without answering the question
- Citations reference wrong issuer or filing vs expected_bindings

Score **1.0** when answer synthesizes retrieved evidence and addresses the question.
