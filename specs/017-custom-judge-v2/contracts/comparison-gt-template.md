# Contract: Comparison-Structured Ground Truth Template (017)

**Applies to**: `answer_type: comparison_structured` items (≥40 in v2.0 dev split)

## Question patterns

- Cross-filing narrative comparison ("Do both filings discuss X in Item 7?")
- Multi-period qualitative comparison (non-numeric)
- FinAgentBench-style agentic retrieval across ≥2 accessions

## Canonical answer template

```
Both {label_a} and {label_b} discuss {topic} in {section_a}{optional_section_b_clause}.
```

Where:
- `{label_a}`, `{label_b}` = fiscal labels from bound filings (e.g., FY2025 10-K, FY2024 10-K)
- `{topic}` = normalized topic phrase from question
- `{section_a}` = structural anchor in filing A (Item 7 MD&A, Item 1A, etc.)
- `{optional_section_b_clause}` = ` and {section_b}` when sections differ across filings

## Required claims (minimum 3)

Claims must be **structured**, not boilerplate phrases. The judge scores whether both filings are covered and compared.

1. **Filing A claim**: atomic fact grounded in filing A (company + form/year + section).
2. **Filing B claim**: atomic fact grounded in filing B (same structure).
3. **Cross-filing synthesis claim**: compares or contrasts both filings on the topic using natural language (e.g. shared themes, differences, relative emphasis). Examples:
   - "Both companies highlight international operations as a major risk theme."
   - "Revenue growth is a shared theme across both filings in Item 7 MD&A."

Optional additional per-filing claims (max 8 total) for multi-hop reasoning.

**Not required**: fixed phrases such as "The comparison spans both bound filings." Validation uses semantic structure (`comparison_claims_are_structured` in `comparison_gt.py`).

## Validation rules

| Check | Fail reason |
|-------|-------------|
| `<2` accessions in bindings | `comparison_bindings` |
| answer missing both-filings pattern | `invalid_answer_type` |
| `<3` claims or missing per-filing + cross structure | `required_claims` |
| question asks YoY numeric metric | use `numeric` answer_type instead |

### Semantic cross-filing detection

A cross-filing claim is recognized when it:
- mentions both compared entities in one claim, or
- uses comparative language (`compare`, `contrast`, `shared`, `both companies/filings`, etc.), or
- references two filing years/forms in one sentence.

Per-filing claims must each anchor to a single filing (entity-specific, not the synthesis claim).

## Partial credit (judge)

Value alignment scored per judge v3.1 graded VA policy:
- Supported claim / total claims ratio
- Floor 0.25 when any claim substantively present (016 policy carry-forward)

## Generation prompt constraints

Generator MUST (`configs/benchmarks/inspiration_profiles/finagentbench.yaml`):
- Read section text from both bound filings before emitting answer
- Emit `answer_type: comparison_structured` in item JSON
- Emit 3–8 `required_claims`: per-filing A, per-filing B, optional hops, cross-filing synthesis
- Use natural language for synthesis; judge assesses coverage, not fixed wording

Post-parse `normalize_v2_item` may append the canonical answer as a synthesis claim when claims are sparse but valid otherwise.

## Example

**Question**: Do the FY2025 and FY2024 10-K filings both discuss supply chain risk in MD&A?

**Answer**: Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A.

**Claims**:
1. FY2025 10-K discusses supply chain risk in Item 7 MD&A.
2. FY2024 10-K discusses supply chain risk in Item 7 MD&A.
3. Both filings emphasize supply chain risk as a material factor in Item 7 MD&A.
