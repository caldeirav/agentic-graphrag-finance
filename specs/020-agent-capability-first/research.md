# Research: Agent Capability-First Numeric Synthesis

**Date**: 2026-06-22

## Problem Statement

Graph-full variant on paper-v1.1 repaired run: primary-evidence **xbrl** stratum (26 items) shows MRR≈0.96, abstention 0%, **task_success=0**. All failures have `value_alignment=0`.

## Failure Taxonomy (repaired paper-v1.1)

| Mode | Count | Description |
|------|-------|-------------|
| synthesis_template_dump | 18 | Answer is "Based on N evidence chunk(s): …" |
| numeric_xbrl_miss | 8 | Wrong concept, period, or missing numeric extraction |

Many items exhibit both: retrieval finds correct XBRL chunks but synthesis does not extract the asked metric for the asked period.

## Root Causes

### 1. Template synthesis fallback (live path)

`synthesis.py` runs a ladder of deterministic `_try_synthesize_*` handlers, then `_synthesize_with_llm`, then `_synthesize_template` which emits chunk dumps. Live path should not use template dumps.

### 2. Weak temporal binding

Questions explicitly ask for FY2025; macro router binds latest filing (2026/Q1). Benchmark `expected_bindings.fiscal_periods` exists but was not passed into macro planner prompts.

### 3. No XBRL fact disambiguation

When multiple XBRL facts rank highly, synthesis concatenates chunks instead of selecting the fact matching the question metric (e.g., debt-to-equity vs total debt).

## Decision: Capability-First vs Keyword Handlers

**Chosen**: Structured output contract + LLM skills + prompt enrichment.

**Rejected**: Expanding `_try_synthesize_numeric_xbrl` keyword routing—brittle, untestable at scale, violates agent design goals.

**Mock/CI**: Keep deterministic handlers when `USE_MOCK_LLM=1` for fast unit tests.

## References

- Investigation pack: `reports/repro-paper-v1.1/` (repaired)
- Prior feature: `specs/019-agent-failure-investigation/`
- Taxonomy: `src/evaluation/reproduction/investigation/taxonomy.py`

## 26-Item Cohort IDs

v2-financebench-0428, 0436, 0449, 0460, 0461, 0467, 0495, 0534, 0536, 0547, 0548, 0563, 0575, 0579, 0582, 0583, 0590, 0592, 0600, 0610, 0625, 0638, 0666, 0667, 0676, 0684
