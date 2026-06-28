# Data Model: Agent Failure Investigation and Remediation (019)

**Feature**: 019-agent-failure-investigation | **Date**: 2026-06-20

## Overview

Evaluation-layer artifacts for tier-1 agent failure triage, cohort debug, and pre-repro validation. All models use Pydantic v2 in `src/models/investigation.py` (new module).

---

## EngineeringFailureClass

Enum of auto-suggested failure codes (distinct from 018 `FailureClass` human annotation).

| Value | Meaning |
|-------|---------|
| `binding_error` | Wrong filing set, form type, company, or fiscal period |
| `retrieval_label_mismatch` | High MRR/nDCG but judge retrieval_fidelity=0 |
| `synthesis_template_dump` | Generic evidence-list answer despite good retrieval |
| `numeric_xbrl_miss` | Numeric question/GT; XBRL evidence retrieved; answer not grounded |
| `comparison_narrative_miss` | Comparison item without substantive cross-filing answer |
| `abstention` | Empty or explicit insufficient-evidence answer |
| `gt_issue_suspected` | Signals suggest GT scale/strictness issue (advisory) |

---

## FailureInvestigationRow

One merged investigation record (HTML row + CSV row + report drill-down).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `item_id` | string | yes | Benchmark item identifier |
| `priority_tier` | int | no | From review queue |
| `priority_score` | float | no | Queue rank score |
| `inspiration_profile` | string | no | financebench / finder / finagentbench |
| `question` | string | yes | Benchmark question |
| `expected_answer` | string | yes | Ground truth answer |
| `required_claims` | list[string] | no | Comparison claims |
| `expected_section_paths` | list[string] | no | Bound section paths |
| `agent_answer` | string | no | From repro results |
| `citation_excerpts` | list[CitationExcerpt] | no | Top N citations with text |
| `outcome_score` | float | no | Value alignment / task success |
| `mrr` | float | no | Ranking metric |
| `ndcg_at_10` | float | no | Ranking metric |
| `judge_status` | string | no | ok / degraded / pending |
| `judge_rationale` | string | no | Truncated for HTML |
| `judge_scores` | dict[str, float] | no | value_alignment, synthesis_grounding, etc. |
| `synthesis_path` | string | no | e.g. live_llm, numeric_xbrl_deterministic, template |
| `suggested_failure_class` | EngineeringFailureClass | no | Rule-based suggestion |
| `suggested_failure_detail` | string | no | Rule hit explanation |
| `human_failure_class` | string | no | Latest 018 annotation class |
| `human_annotation_notes` | string | no | Latest annotation notes |
| `edgar_links` | list[EdgarFilingLink] | no | Per bound accession |
| `corpus_excerpts` | list[CorpusExcerpt] | no | Section text snippets |
| `materialization_audit` | MaterializationAudit | no | Expected vs visited |
| `graph_context_href` | string | no | Relative link to subgraph panel |
| `graph_context_inline` | bool | no | True when pre-rendered embed available |
| `repro_result_path` | string | no | Path to source results.json |

---

## CitationExcerpt

| Field | Type | Description |
|-------|------|-------------|
| `chunk_node_id` | string | Graph chunk id |
| `accession` | string | Filing accession |
| `section_id` | string | Section slug |
| `excerpt` | string | Truncated text |

---

## EdgarFilingLink

| Field | Type | Description |
|-------|------|-------------|
| `accession` | string | EDGAR accession |
| `form_type` | string | 10-K / 10-Q |
| `period_end` | date | Fiscal period end |
| `url` | string | Human-readable filing index URL |
| `link_omitted_reason` | string | When url absent |

---

## CorpusExcerpt

| Field | Type | Description |
|-------|------|-------------|
| `section_path` | string | `{accession}/{section}` |
| `text` | string | Excerpt or `[corpus pointer]` |
| `source` | enum | `bundle_section` / `pointer` |

---

## MaterializationAudit

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | string | Bundle corpus snapshot |
| `expected_accessions` | list[string] | From benchmark bindings |
| `visited_accessions` | list[string] | From trajectory / citations |
| `expected_section_paths` | list[string] | From benchmark item |
| `visited_section_paths` | list[string] | From trajectory |
| `cited_chunk_node_ids` | list[string] | Answer citations |
| `binding_miss` | bool | Expected sections not visited |

---

## Tier1CohortFile

Frozen pre-repro validation cohort (all tier-1 queue items).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | `"1.0.0"` |
| `source_queue_path` | string | yes | Path to review_queue.json |
| `source_queue_hash` | string | yes | sha256 of queue file |
| `exported_at` | datetime | yes | Freeze timestamp |
| `item_ids` | list[string] | yes | All tier-1 ids (~84) |
| `entries` | list[Tier1CohortEntry] | no | Optional priority metadata per id |

---

## Tier1CohortEntry

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | string | |
| `priority_tier` | int | |
| `priority_score` | float | |

---

## CohortDebugSummary

Per-item output from cohort debug (re-run or replay).

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | string | |
| `variant_id` | string | graph-full |
| `mode` | enum | `rerun` / `replay` |
| `macro_plan_summary` | string | Intent + filing scope |
| `filing_set` | list[string] | Accessions bound |
| `meso_decisions` | list[string] | Section routes |
| `micro_evidence_count` | int | Chunks retrieved |
| `synthesis_path` | string | |
| `citation_count` | int | |
| `outcome_score` | float | |
| `weakest_judge_criterion` | string | |
| `suggested_failure_class` | EngineeringFailureClass | |
| `failure_flags` | list[string] | e.g. binding_miss, template_dump |
| `trace_event_count` | int | JSONL events captured |

---

## CohortValidationReport

Output of `repro cohort-validate`.

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | `"1.0.0"` |
| `cohort_hash` | string | Input tier1_cohort.json hash |
| `manifest_tag` | string | paper-v1.1 |
| `run_at` | datetime | |
| `output_dir` | string | Repro output path |
| `item_count` | int | |
| `tier1_zero_count` | int | outcome=0 on cohort |
| `strong_retrieval_zero_count` | int | MRR≥0.5 or nDCG≥0.3 & outcome=0 |
| `synthesis_path_counts` | dict[string, int] | |
| `engineering_failure_counts` | dict[string, int] | |
| `thresholds` | CohortGateThresholds | Applied thresholds |
| `baseline_comparison` | CohortBaselineComparison | vs paper-v1.0 snapshot |
| `passed` | bool | All thresholds met |

---

## CohortGateThresholds

Configured in `releases/paper-v1.1/manifest.yaml`.

| Field | Type | Description |
|-------|------|-------------|
| `baseline_snapshot_path` | string | Prior cohort_validation_report.json |
| `max_strong_retrieval_zero_outcome` | int | Max allowed |
| `max_mrr_ok_va_zero` | int | Max MRR≥0.5 & VA=0 |
| `min_synthesis_template_dump_share_reduction` | float | vs baseline share |
| `require_regression_suite_pass` | bool | CI suite must pass |

---

## CohortBaselineComparison

| Field | Type | Description |
|-------|------|-------------|
| `baseline_strong_retrieval_zero_count` | int | From baseline snapshot |
| `delta_strong_retrieval_zero_count` | int | current - baseline |
| `delta_percent` | float | Percent change |

---

## CohortGateOverrideRecord

Append-only audit when `--force-cohort-gate` used.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | |
| `operator` | string | env USER or flag |
| `manifest_tag` | string | |
| `failed_thresholds` | list[string] | |
| `rationale` | string | Required flag value |

---

## TaxonomyMapping

Static default mapping engineering → 018 human class (documented in contract).

| EngineeringFailureClass | Default Human Class |
|---------------------------|---------------------|
| binding_error | agent_failure |
| retrieval_label_mismatch | agent_failure |
| synthesis_template_dump | agent_failure |
| numeric_xbrl_miss | agent_failure |
| comparison_narrative_miss | agent_failure |
| abstention | agent_failure |
| gt_issue_suspected | gt_too_strict |

Reviewer MAY override human class independently.

---

## Relationships

```text
ReviewQueueEntry ──► Tier1CohortFile ──► CohortValidationReport
BenchmarkResult ──► FailureInvestigationRow ◄── ItemAnnotation (018)
BenchmarkResult ──► CohortDebugSummary
CohortValidationReport ──► CohortGateThresholds (manifest)
```

---

## Validation Rules

- `Tier1CohortFile.item_ids` MUST equal all tier-1 entries in source queue at freeze time
- `FailureInvestigationRow.suggested_failure_class` MUST NOT overwrite `human_failure_class`
- `CohortValidationReport.passed` false ⇒ `repro run-all` for paper-v1.1 MUST exit non-zero unless override recorded
- `EdgarFilingLink.url` MUST be omitted (not empty invalid URL) when `link_omitted_reason` set
