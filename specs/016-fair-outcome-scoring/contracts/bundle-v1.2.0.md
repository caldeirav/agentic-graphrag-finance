# Contract: Custom-Judge Bundle v1.2.0 (016)

**Path**: `data/benchmarks/custom-judge/v1.2.0/`  
**Parent**: `v1.1.0` (immutable, retained)

## Required artifacts

| File | Purpose |
|------|---------|
| `manifest.json` | version `1.2.0`, `parent_version: "1.1.0"` |
| `items.jsonl` | full dev split with migrations |
| `CHANGELOG.md` | item-level change log |
| `feasibility_report.json` | publish gate results |
| `reachability_report.json` | section reachability for answer-GT items |

## Migration categories (from v1.1.0)

1. **Question–binding year alignment**: question fiscal years match `expected_bindings.fiscal_periods`
2. **Section reachability**: answer-GT `expected_section_paths` resolve in corpus graph index
3. **Required claims**: narrative answer-GT has 2–8 atomic `required_claims` for graded VA
4. **Relevance refresh**: `relevance_labels.json` / `labels_hash` recomputed for touched items

## Publish gates (blocking)

| Gate | Rule |
|------|------|
| `comparison_bindings` | comparison-tagged items have ≥2 accessions in bindings |
| `reference_corpus` | referenced accession exists in corpus index |
| `required_claims` | every non-numeric answer-GT has 1–8 claims |
| `rubric_route` | rubric-only items have non-empty rubric |
| `question_binding_year_mismatch` | no answer-GT item with disjoint question vs binding years |
| `section_reachability` | every answer-GT item has `reachable: true` in reachability report |

## Release manifest update

`releases/paper-v1.0/manifest.yaml`:

```yaml
custom_judge_version: "1.2.0"
custom_judge_bundle_path: data/benchmarks/custom-judge/v1.2.0
```

Relevance hash fields recomputed on publish.
