# Research: Agent Failure Investigation and Remediation (019)

**Feature**: 019-agent-failure-investigation | **Date**: 2026-06-20

## R1 — Failure investigation pack architecture

**Decision**: Single **`build_failure_investigation_rows()`** in `evaluation/reproduction/investigation/pack.py` merges inputs from: (1) `review_queue.json` or item-id list, (2) `graph-full/results.json`, (3) draft bundle `items/dev.jsonl` + `annotations.jsonl`, (4) bundle corpus for section excerpts, (5) `trajectory_snapshot` / synthesis path from results. Output: `failure_investigation.html` + `failure_investigation.csv` co-located with repro output; same row builder feeds **`report_render.py`** drill-down extension.

**Rationale**: Eliminates split between 014 repro report and 018 review pack; one source of truth for investigation fields (FR-001, FR-002).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Extend review_pack.py only | Lacks agent answer depth from repro results |
| Separate standalone tool | Duplicates row logic; drill-down diverges |

---

## R2 — Engineering failure taxonomy rules

**Decision**: Rule-ordered classifier in `taxonomy.py` (first match wins):

1. `abstention` — empty answer or explicit insufficient-evidence text
2. `binding_error` — judge rationale keywords (wrong company/form/year) OR expected vs visited filing set mismatch in materialization audit
3. `synthesis_template_dump` — answer matches template prefix ("Based on" + chunk list) with outcome=0
4. `numeric_xbrl_miss` — numeric GT, MRR≥0.5, XBRL section path, answer lacks parseable number matching GT scale
5. `comparison_narrative_miss` — comparison item, outcome=0, no cross-filing contrast verbs in answer
6. `retrieval_label_mismatch` — MRR≥0.5 AND judge `retrieval_fidelity`=0
7. `gt_issue_suspected` — high retrieval + numeric answer present but VA=0 AND GT scale/units anomaly heuristics

Default mapping to 018 human classes documented in `contracts/taxonomy-suggestion.md`.

**Rationale**: Tier-1 failure clusters from paper-v1.0 triage; deterministic rules meet SC-002 auditability.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| LLM classifier | Non-deterministic; costly for 84-item export |
| Judge-only labels | Judge rationale inconsistent; misses synthesis_path signal |

---

## R3 — SEC EDGAR filing links

**Decision**: `edgar_links.py` builds `https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{accession}-index.htm` from bundle `corpus/graphs/{TICKER}/{snapshot}.manifest.json` filing_refs (CIK + accession). Fallback: accession-only display with `link_omitted_reason: missing_cik` when CIK unavailable.

**Rationale**: Reuses existing `FilingRef.source_uri` pattern from ingestion; offline bundle manifest has CIK (FR-002, SC-004).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Live EDGAR lookup at export time | Breaks offline report requirement |
| Generic sec.gov search links | Not human-readable filing pages |

---

## R4 — Materialization audit fields

**Decision**: Per item, compute:
- `expected_snapshot_id` from bundle manifest
- `expected_accessions` / `expected_section_paths` from benchmark item
- `visited_accessions` / `visited_section_paths` from `trajectory_snapshot` or citation accessions
- `cited_chunk_node_ids` from answer citations
- `binding_miss` boolean when expected sections not in visited set

Source: bundle manifest + `BenchmarkResult.trajectory_snapshot` + citations.

**Rationale**: Surfaces macro/route errors without MLflow UI (User Story 1, FR-001).

---

## R5 — Cohort debug trace output

**Decision**:
- **Default mode**: subset of `ReproRunner.run_variant()` with `item_ids` from cohort file, `trace_level: normal`, `trace_json: true` → stderr JSONL via existing console trace; plus **`cohort_debug/{item_id}.summary.json`** aggregating macro plan, filing_set, synthesis_path, citation_count, outcome, weakest judge criterion from results + trace events.
- **Replay mode** (`--replay`): read existing `results.json` + `trajectory_snapshot` + optional MLflow artifact paths; emit same summary schema without agent invocation.

**Rationale**: Clarification session (re-run default); reuses 007 trace registry (FR-005, FR-006).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| MLflow-only debug | Requires UI; fails SC-006 offline diagnosis goal |
| Full verbose repro for 200 items | Too slow for iteration |

---

## R6 — Cohort gate enforcement

**Decision**:
- `tier1_cohort.json` frozen from full tier-1 `review_queue.json` (~84 ids + provenance hash)
- `repro cohort-validate --manifest releases/paper-v1.1/manifest.yaml` runs agent+judge on cohort (graph-full), writes `cohort_validation_report.json` with: tier-1 zero count, `max_mrr_ok_va_zero` equivalent on cohort, synthesis_path histogram, suggested taxonomy distribution
- Thresholds in `manifest.cohort_gate_thresholds` (extend paper-v1.1 yaml)
- `repro run-all` checks latest passing cohort validation for paper-v1.1 tag; **exit 1** if missing/failed unless `--force-cohort-gate` with audit append to `cohort_gate_overrides.jsonl`

**Rationale**: Clarification hard-block; thresholds configurable not hard-coded (FR-009, Assumptions).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Warn only | Operator bypasses gate silently |
| Cap cohort at 60 | Clarification rejected; full 84 required |

---

## R7 — Graph context presentation

**Decision**: Link-first:
- Generate `graph_context/{item_id}.html` static subgraph panel from bundle graphml + cited node ids (read-only, offline)
- Investigation pack links to panel; if bundle contains pre-rendered `corpus/graph_context/{item_id}.json`, embed inline iframe/section in drill-down

**Rationale**: Clarification link-first; avoids bloating main report HTML (FR-003).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Inline embed always | 84 items × subgraph HTML too heavy |
| Defer graph context | Loses citation-to-graph investigation value |

---

## R8 — Agent remediation priorities (from tier-1 triage)

**Decision**: Three shipped remediation clusters with regression fixtures under `tests/regression/failure_modes/`:

| Cluster | Target | Evidence |
|---------|--------|----------|
| **M1 Macro binding** | 10-K vs 10-Q, fiscal period, multi-company disambiguation | finagentbench judge rationales |
| **M2 Numeric synthesis** | Extend `_try_synthesize_numeric_xbrl`; block template fallback when ranked XBRL score > 0 | financebench MRR=1 VA=0 |
| **M3 Template guard** | Skip `_synthesize_template` chunk-dump when deterministic handler eligible | ~59% of partial repro zeros |

Comparison narrative improvements (M4) as stretch if M1–M3 land early.

**Rationale**: FR-007; aligns with observed failure frequencies; each cluster has CI regression case.

---

## R9 — Cohort gate threshold defaults (paper-v1.1)

**Decision**: Initial `cohort_gate_thresholds` in paper-v1.1 manifest (operator-tunable):

```yaml
cohort_gate_thresholds:
  baseline_snapshot_path: reports/repro-paper-v1.0/cohort_validation_report.json
  max_strong_retrieval_zero_outcome: 63        # 25% reduction from ~84 baseline
  max_mrr_ok_va_zero: 10                       # stricter than smoke 12 on 84 items
  min_synthesis_template_dump_share_reduction: 0.15
  require_regression_suite_pass: true
```

**Rationale**: SC-003 (25% reduction), SC-005 (2h budget); baseline snapshot pinned to paper-v1.0 cohort run.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Hard-code in Python | Assumption defers to manifest |
| Same smoke thresholds | Smoke uses ~50 items; cohort is 84 |

---

## R10 — Integration with 018 review CLI

**Decision**: Add `benchmark-dataset review export-investigation` accepting same flags as `export-sheet` (`--queue-file`, `--repro-input`, `--draft`); quality_summary extended with `engineering_failure_counts` and `cohort_validation_status`.

**Rationale**: FR-010; minimal new CLI surface.
