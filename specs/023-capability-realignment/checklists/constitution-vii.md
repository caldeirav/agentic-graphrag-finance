# Constitution VII Checklist: Capability Realignment (023)

**Feature**: [spec.md](../spec.md) | **Principle**: `.specify/memory/constitution.md` VII

Complete before merge to main investigation branch.

## Remediation ladder compliance

- [x] **Rung 1** — Structured answer contract is sole live numeric output (no chunk dumps)
- [x] **Rung 2** — Fiscal period labels + temporal anchor in resolution/planner prompts
- [x] **Rung 3** — `resolve_xbrl_facts` is primary disambiguation (including 2-fact ratios)
- [x] **Rung 4** — Cohort gate on `xbrl_numeric_cohort.json` before full repro (runs through m4b)

## Prohibited patterns (live path)

- [x] No new `_try_synthesize_*` keyword handlers
- [x] No live `ratio_pair_resolution` / `point_fact_selection` / `html_table_fallback`
- [x] No numeric fallthrough to `structured_llm` / `live_llm` (except **0600** macro path — open)
- [x] No LLM arithmetic in prose for ratio answers (Python compute only)

## Allowed deterministic code

- [x] `compute_numeric_answer` — Python math after fact selection
- [x] `xbrl_resolution_validate` — post-selection rejection only
- [x] `numeric_evidence_enrichment` — surfaces chunks; LLM still selects
- [x] `xbrl_taxonomy_index` / `ratio_entry_roles` — index-time metadata + role assignment (not LLM routers)
- [x] `slice_expansion` — repro/eval layer only
- [x] Mock/CI deterministic paths when `USE_MOCK_LLM=1`

## Complexity Tracking

- [x] plan.md table reviewed and signed off
- [x] Each exception has rejected alternative + sunset note

## Verification artifacts

- [ ] `audit_cohort_synthesis_paths.py` PASS on latest cohort dir (**FAIL**: 0600 live_llm on m4b)
- [x] `test_no_live_heuristic_imports.py` PASS
- [x] `test_no_numeric_llm_fallback.py` PASS

## Sign-off

| Reviewer | Date | M1 | M2 | M3 | M4b |
|----------|------|----|----|-----|-----|
| Operator | | | | | 0548 abstain ✓; SC-002 pending |
