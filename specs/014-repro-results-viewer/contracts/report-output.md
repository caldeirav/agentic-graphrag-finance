# Reproduction Report Output Contract (014)

## HTML report artifact

Default output:

```text
<output>/report.html
```

Optional companion assets:

```text
<output>/assets/
```

The report must be fully viewable offline after generation.

## Required sections

1. **Run summary**
   - release tag, run id, wall-clock
   - defer/resume flags when present
   - per-variant inclusion/exclusion counts
2. **Paper tables**
   - headline, by_profile, variant_delta, trajectory_audit
   - copy actions: LaTeX / CSV / Markdown
3. **Variant comparison**
   - primary metrics across variants
4. **Item drill-down**
   - filterable rows by variant/profile/judge status
   - expandable detail with answer/citation summary and trajectory pointer
5. **Investigation aids**
   - status highlights (`degraded`, `pending`, `not_evaluable`)
   - structural miss and delta-vs-baseline highlights

## LaTeX-only mode

When `--format latex-only` is selected, write table snippets to stdout:

- deterministic ordering by requested table id(s)
- include provenance comments (`release_tag`, counts)
- retain 012 metric names

## Display formatting

- Numeric value display follows report formatting rules but source values remain unchanged in copied CSV.
- Rounding and naming must remain consistent with 012 export contract semantics.

