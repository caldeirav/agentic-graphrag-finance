# Contract: Custom-Judge Bundle v1.1.0 (016)

**Path**: `data/benchmarks/custom-judge/v1.1.0/`  
**Parent**: `v1.0.0` (immutable, retained)

## Required artifacts

| File | Purpose |
|------|---------|
| `manifest.json` | version `1.1.0`, `parent_version: "1.0.0"` |
| `items.jsonl` | full dev split with migrations |
| `CHANGELOG.md` | item-level change log |
| `feasibility_report.json` | publish gate results |

## CHANGELOG entry schema

```markdown
### {item_id}
- **change_types**: question | bindings | ground_truth | rubric_route
- **summary**: one-line operator description
- **requires_agent_rerun**: true | false
```

## Migration categories (from spec)

1. **Rubric-only routing**: comparison / multi-hop / reference-following → `answer=null`, rubric populated
2. **Required claims**: non-numeric answer-GT → `required_claims[]`
3. **Binding fixes**: infeasible comparison partners corrected or item removed
4. **Question clarity**: ambiguous wording tightened (agent rerun)

## Publish gates (blocking)

| Gate | Rule |
|------|------|
| `comparison_bindings` | comparison-tagged items have ≥2 accessions in bindings |
| `reference_corpus` | referenced accession exists in corpus index |
| `required_claims` | every non-numeric answer-GT has 1–8 claims |
| `rubric_route` | rubric-only items have non-empty rubric |

## Release manifest update

`releases/paper-v1.0/manifest.yaml`:

```yaml
custom_judge_version: "1.1.0"
custom_judge_bundle_path: data/benchmarks/custom-judge/v1.1.0
```

Relevance hash fields recomputed on publish.
