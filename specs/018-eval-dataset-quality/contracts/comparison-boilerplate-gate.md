# Contract: Comparison Boilerplate Gate (018)

**Feature**: 018-eval-dataset-quality | **Extends**: [comparison-gt-template.md](../../017-custom-judge-v2/contracts/comparison-gt-template.md)

## New function

`is_boilerplate_comparison_answer(answer: str) -> bool` in `evaluation/generation/comparison_gt.py`

Returns **true** when ALL hold:

1. `_BOTH_FILINGS_PATTERN.search(answer)` is not None (section co-occurrence template)
2. `_CROSS_VERB.search(answer)` is None (no compare/contrast/differ language)
3. Normalized answer length after stripping template tokens `< 25` words
4. No numeric contrast (no second distinct percentage or dollar figure)

## Validation integration

`validate_comparison_structured` MUST append `boilerplate_comparison_answer` when `is_boilerplate_comparison_answer` returns true.

Publish gate (v2.0.1+): `boilerplate_comparison_count == 0` in `scorability_report.json`.

## Scorability report extension

```json
{
  "boilerplate_comparison_count": 0,
  "borderline_comparison_item_ids": ["v2-finagentbench-0197"]
}
```

`borderline_comparison_item_ids`: passes auto gate but `comparison_answer_informativeness_score < 0.5` (heuristic: has pattern but lacks cross-verb and short length 25–40 words) — human audit required.

## Prompt update

`configs/benchmarks/inspiration_profiles/finagentbench.yaml` MUST instruct: canonical answer MUST state **compared conclusion** (difference, similarity, or relative emphasis), not only that both filings mention a topic in a section.

## Example

**Reject (boilerplate)**:
> Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K discuss geopolitical risks in Item 1A. Risk Factors.

**Accept (substantive)**:
> Caterpillar frames geopolitical risk around supply-chain and end-market cyclicality, while Exxon Mobil emphasizes sanctions, national oil company actions, and commodity price volatility in their 2025 10-K risk disclosures.
