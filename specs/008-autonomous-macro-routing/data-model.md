# Data Model: Autonomous Macro Routing (008)

**Branch**: `008-autonomous-macro-routing` | **Date**: 2026-05-23

## Overview

Macro routing produces a **validated filing binding** before meso/micro stages. Data flows: optional CLI scope → (optional) deterministic pre-bind → **MacroBindingProposal** → **BindingValidationResult** → **`filing_set`** + **MacroPlan** in `AgentState` → **TrajectoryRecord** / MLflow artifact.

## Entities

### MacroBindingProposal (new)

LLM or deterministic fast-path output; not trusted until validated.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `intent_summary` | string | yes | Short query intent |
| `comparison_mode` | ComparisonMode | no | `yoy`, `qoq`, `sequential`, `none` |
| `anchor` | string | no | e.g. `latest_quarter`, `prior_quarter`, `latest_annual` |
| `period_labels` | list[string] | no | e.g. `FY2025-Q1` |
| `proposed_accessions` | list[string] | no | Explicit accession picks |
| `is_comparison` | bool | no | Derived or stated |
| `quarterly_metric_cue` | bool | no | YoY quarterly pairing |
| `proposal_source` | enum | yes | `llm` \| `deterministic` \| `cli` |
| `raw_llm_text` | string | no | Audit only |

### BindingValidationResult (new)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | enum | yes | `approved` \| `failed` \| `narrowed` |
| `approved_accessions` | list[string] | yes | Final set (may be empty on fail) |
| `comparison_mode` | ComparisonMode | yes | After validation |
| `failure_codes` | list[string] | no | e.g. `missing_prior_year_quarter`, `cli_conflict` |
| `rationale` | string | yes | Human-readable |
| `narrowed_from` | list[string] | no | When status=`narrowed` |

### MacroBindingRecord (new, trajectory)

Superset persisted to MLflow `macro_binding.json` and console trace.

| Field | Type | Notes |
|-------|------|-------|
| `binding_source` | string | `cli_prebound` \| `autonomous` |
| `proposal` | MacroBindingProposal | nullable if CLI-only |
| `validation` | BindingValidationResult | |
| `filing_refs` | list[FilingRef] | Resolved refs post-validation |
| `scope_manifest_id` | string | Snapshot id |

### MacroPlan (extended)

Existing `MacroPlan` in `models/query.py` gains optional fields:

| Field | Type | Notes |
|-------|------|-------|
| `validation` | BindingValidationResult | optional embed |
| `binding_source` | string | |

### MisalignmentReport

| Code | Meaning |
|------|---------|
| `missing_comparison_partner` | YoY/QoQ partner not in manifest |
| `ambiguous_comparison` | QoQ and YoY cues conflict |
| `cli_nl_conflict` | CLI scope vs proposal irreconcilable |
| `empty_corpus` | No filings in snapshot |
| `invalid_accession` | Proposal accession not in manifest |

## State transitions (`AgentState`)

```text
[ask start]
  → filing_set from CLI (maybe full corpus today — 008: [] if scope empty)
  → macro_router
       → proposal (LLM or deterministic)
       → validate
       → approved: filing_set + macro_plan + macro_binding_record
       → failed: status=FAILED/PARTIAL, answer=scope error text, no meso
       → narrowed: filing_set single + rationale downgrade comparison
  → intent_router (unchanged)
  → meso/micro (only if filing_set valid)
```

## Benchmark extensions

`BenchmarkItem` (existing) — per macro eval row:

| Field | Required for macro slice |
|-------|--------------------------|
| `expected_bindings.accessions` | yes |
| `multi_filing_required` | yes (new optional field on JSONL or tags) |
| `temporal_scope` | yes (structured, not NL-only) |

## Validation rules (deterministic)

1. Every approved accession ∈ `snapshot.manifest.filing_refs`.
2. If `comparison_mode` in (`yoy`, `qoq`): len(accessions) ≥ 2 or fail.
3. YoY quarterly: accessions match pairing rule on manifest labels.
4. YoY annual: two latest 10-K by period_end.
5. QoQ: latest + prior 10-Q sequential.
6. CLI pre-bound set must equal proposal accessions when both present, else `cli_nl_conflict`.
7. Narrowing: only when exactly one filing survives filter; set `comparison_mode=none`.

## Relationships

```text
GraphSnapshot.manifest.filing_refs
    ↑ validates against
MacroBindingProposal
    → BindingValidationResult
    → filing_set (list[FilingRef])
    → TrajectoryRecord.plan + macro_binding artifact
```
