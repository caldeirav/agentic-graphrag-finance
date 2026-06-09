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

1. **Filing A claim**: `{label_a} discusses {topic} in {section_a}.`
2. **Filing B claim**: `{label_b} discusses {topic} in {section_b}.` (or same section if identical)
3. **Cross-filing claim**: `The comparison spans both bound filings.`

Optional additional claims (max 8 total):
- Sub-topic claims (e.g., specific risk named in question)
- Negation claims when question asks about absence in one filing

## Validation rules

| Check | Fail reason |
|-------|-------------|
| `<2` accessions in bindings | `comparison_bindings` |
| answer missing both filing labels | `invalid_answer_type` |
| `<3` required_claims | `required_claims` |
| claim missing filing attribution | `required_claims` |
| question asks YoY numeric metric | use `numeric` answer_type instead |

## Partial credit (judge)

Value alignment scored per judge v3.1 graded VA policy:
- Supported claim / total claims ratio
- Floor 0.25 when any claim substantively present (016 policy carry-forward)

## Generation prompt constraints

Generator MUST:
- Read section text from both bound filings before emitting answer
- Emit `answer_type: comparison_structured` in item JSON
- Derive claims from answer decomposition, not separate rubric prose

## Example

**Question**: Do the FY2025 and FY2024 10-K filings both discuss supply chain risk in MD&A?

**Answer**: Both FY2025 and FY2024 10-K filings discuss supply chain risk in Item 7 MD&A.

**Claims**:
1. FY2025 10-K discusses supply chain risk in Item 7 MD&A.
2. FY2024 10-K discusses supply chain risk in Item 7 MD&A.
3. The comparison spans both bound filings.
