# Constitution VII Checklist: Capability Realignment (023)

**Feature**: [spec.md](../spec.md) | **Principle**: `.specify/memory/constitution.md` VII

Complete before merge to main investigation branch.

## Remediation ladder compliance

- [ ] **Rung 1** — Structured answer contract is sole live numeric output (no chunk dumps)
- [ ] **Rung 2** — Fiscal period labels + temporal anchor in resolution/planner prompts
- [ ] **Rung 3** — `resolve_xbrl_facts` is primary disambiguation (including 2-fact ratios)
- [ ] **Rung 4** — Cohort gate on `xbrl_numeric_cohort.json` before full repro

## Prohibited patterns (live path)

- [ ] No new `_try_synthesize_*` keyword handlers
- [ ] No live `ratio_pair_resolution` / `point_fact_selection` / `html_table_fallback`
- [ ] No numeric fallthrough to `structured_llm` / `live_llm`
- [ ] No LLM arithmetic in prose for ratio answers (Python compute only)

## Allowed deterministic code

- [ ] `compute_numeric_answer` — Python math after fact selection
- [ ] `xbrl_resolution_validate` — post-selection rejection only
- [ ] `numeric_evidence_enrichment` — surfaces chunks; LLM still selects
- [ ] `slice_expansion` — repro/eval layer only
- [ ] Mock/CI deterministic paths when `USE_MOCK_LLM=1`

## Complexity Tracking

- [ ] plan.md table reviewed and signed off
- [ ] Each exception has rejected alternative + sunset note

## Verification artifacts

- [ ] `audit_cohort_synthesis_paths.py` PASS on latest cohort dir
- [ ] `test_no_live_heuristic_imports.py` PASS
- [ ] `test_no_numeric_llm_fallback.py` PASS

## Sign-off

| Reviewer | Date | M1 | M2 | M3 |
|----------|------|----|----|-----|
| Operator | | | | |
