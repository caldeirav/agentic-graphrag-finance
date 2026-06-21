# Contract: Engineering Failure Taxonomy Suggestion

**Feature**: 019 | **Module**: `evaluation/reproduction/investigation/taxonomy.py`

## Input signals

| Signal | Source |
|--------|--------|
| `outcome_score`, `mrr`, `ndcg_at_10` | `BenchmarkResult.ranking_metrics` |
| `answer.text`, citations | `BenchmarkResult.answer` |
| `judge_verdict.scores`, `rationale` | `BenchmarkResult.judge_verdict` |
| `synthesis_path` | `trajectory_snapshot` or result metadata |
| `materialization_audit.binding_miss` | audit builder |
| `ground_truth.answer`, `answer_type`, `question_type_tag` | bundle item |

## Rule order (first match wins)

1. **abstention** — empty answer OR contains "insufficient evidence" (case insensitive) without numeric grounding
2. **binding_error** — audit `binding_miss` OR rationale matches `(wrong (company|filing|form)|10-K.*10-Q|incorrect (entity|issuer))`
3. **synthesis_template_dump** — answer starts with "Based on" AND lists evidence chunks AND `synthesis_path` in (`template`, `live_llm`)
4. **numeric_xbrl_miss** — numeric GT, MRR≥0.5, expected path contains `XBRL`, answer has no dollar/percent matching GT magnitude
5. **comparison_narrative_miss** — comparison item, outcome=0, answer lacks `_CROSS_VERB` pattern (reuse comparison_gt regex set)
6. **retrieval_label_mismatch** — MRR≥0.5 AND judge `retrieval_fidelity` == 0
7. **gt_issue_suspected** — numeric answer tokens present, VA=0, GT scale heuristic (raw integer vs billion question)

If no rule matches: `suggested_failure_class = null`, `suggested_failure_detail = "unclassified"`.

## Dual-layer mapping (default → 018 human class)

| Engineering | Default human |
|-------------|---------------|
| binding_error | agent_failure |
| retrieval_label_mismatch | agent_failure |
| synthesis_template_dump | agent_failure |
| numeric_xbrl_miss | agent_failure |
| comparison_narrative_miss | agent_failure |
| abstention | agent_failure |
| gt_issue_suspected | gt_too_strict |

Human annotation via 018 `review annotate` remains authoritative for quality summary.

## Tests

- `tests/unit/test_failure_taxonomy.py` — one fixture per rule + mapping table snapshot
