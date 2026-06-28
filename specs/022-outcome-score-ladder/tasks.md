# Tasks: Outcome Score Ladder (022)

**Input**: `/specs/022-outcome-score-ladder/`  
**Prerequisites**: 021 shipped; informal 022 binding (`99e9d48`); baseline `reports/cohort-xbrl-022-debug`  
**Format**: `[ID] [P?] [Story] Description`

**Rule**: Do **not** start phase N+1 until phase N **unit tests pass** and **cohort gate** meets floor (or waiver logged in `research.md`).

---

## Phase 0: Setup

- [x] T001 Create remaining spec artifacts (plan, tasks, quickstart, contracts, fixtures, checklist, gate script)
- [x] T002 [P] Set `.specify/feature.json` to `022-outcome-score-ladder`
- [x] T003 [P] Update `.cursor/rules/specify-rules.mdc` plan pointer to 022
- [x] T004 [P] Add contract schemas under `specs/022-outcome-score-ladder/contracts/`

---

## Phase 1: User Story A — Ratio Pipeline (022b) (P1)

**Goal**: Two-fact percent output for margin, effective tax rate, dividend payout.  
**Targets**: `0548`, `0667`, `0666`, `0592`  
**Gate**: **SC-A** — ≥2/26 `outcome_score > 0`; zero `$ billion` rate/margin/payout answers

### Implementation

- [x] T005 [US-A] Add `RatioPairIntent` + `RatioPairResolution` dataclasses in `src/retrieval/skills/ratio_pair_resolution.py`
- [x] T006 [US-A] Implement `infer_ratio_pair_intent(metric_intent, query)` — map margin/tax/payout to numerator/denominator families
- [x] T007 [US-A] Implement `resolve_ratio_pair(catalog, intent, temporal_intent)` — select two guarded entries with matching annual period
- [x] T008 [US-A] Extend `xbrl_concept_guards.py`: reject statutory/reconciliation tax, OCI-as-payout, single-fact ratio candidates
- [x] T009 [US-A] Extend `compute_numeric_answer()` ratio branch: require two inputs; output `NN.N%` via `computed_value` + `unit=percent`
- [x] T010 [US-A] Wire synthesis: after `classify_metric_intent`, if `metric_type=ratio` → `resolve_ratio_pair` → compute or abstain (no LLM dollar fallback)
- [x] T011 [P] [US-A] Extend `metric-intent.schema.json` / structured answer with `output_unit=percent` for ratio path
- [x] T012 [P] [US-A] Trace field `ratio_pair_resolution_json` on AgentState (optional JSON)

### Tests (must pass before cohort gate)

- [x] T013 [P] [US-A] Unit tests `tests/unit/test_ratio_pair_resolution.py`:
- [x] T014 [P] [US-A] Extend `tests/unit/test_xbrl_concept_guards.py` — statutory tax, OCI payout rejected
- [x] T015 [P] [US-A] Extend `tests/unit/test_numeric_computation.py` — ratio outputs percent only; no `$` in value for rate intents
- [ ] T016 [P] [US-A] Fixtures `tests/fixtures/ratio_pairs/{0548,0667,0666,0592}.json` with catalog excerpts + expected GT percent band
- [x] T017 [P] [US-A] Regression `tests/regression/failure_modes/test_ratio_no_dollar_rate.py` — scan structured payloads for forbidden patterns from `cohort_phase_targets.json`

### Cohort gate A

- [ ] T018 [US-A] Operator: cohort-debug → `reports/cohort-022-phase-a` + judge-batch `--force-rescore`
- [ ] T019 [US-A] Run `specs/022-outcome-score-ladder/scripts/check_phase_gate.py --phase A`
- [ ] T020 [US-A] Record metrics in `specs/022-outcome-score-ladder/research.md` (outcome_gt0, per-target item VA, forbidden-pattern count)

**Checkpoint**: outcome_gt0 ≥ 2; 0548 or 0667 shows VA > 0 on at least one item.

---

## Phase 2: User Story B — Point-Fact Catalog (P1)

**Goal**: Primary annual concepts on calendar-rebound filing; CAT issuer path for 0495.  
**Targets**: `0436`, `0495`, `0534`, `0547`  
**Gate**: **SC-B** — ≥5/26 cumulative `outcome_score > 0`

### Implementation

- [x] T021 [US-B] Add `point_fact_selection.py` with `select_point_fact(catalog, query, metric_intent, temporal_intent) -> PointFactSelection | None`
- [x] T022 [US-B] Concept priority tables: equity (`StockholdersEquity` > components), cash (`CashAndCashEquivalents`), assets (`Assets`)
- [x] T023 [US-B] Scale normalization: detect millions/billions from XBRL `decimals`/`scale` and align display to GT magnitude
- [x] T024 [US-B] Issuer routing: resolve benchmark ticker → accession; CAT FY2025 10-K for 0495 (not XOM rebound)
- [x] T025 [US-B] Wire synthesis point path: catalog → `select_point_fact` → structured render (skip LLM when high confidence)
- [x] T026 [P] [US-B] Extend `build_xbrl_fact_catalog()` annual filter on rebound accession `0000034088-26-000045` for XOM items

### Tests

- [x] T027 [P] [US-B] Unit tests `tests/unit/test_point_fact_selection.py` — equity/cash/assets annual pick; reject `EquityOther`, interim Q1
- [ ] T028 [P] [US-B] Fixtures `tests/fixtures/point_facts/{0436,0495}.json` from Dec-2025 10-K excerpts
- [ ] T029 [P] [US-B] Integration smoke: mock catalog for 0495 selects CAT accession concepts
- [ ] T030 [P] [US-B] Extend `test_xbrl_fact_catalog.py` — primary concept ranking

### Cohort gate B

- [ ] T031 [US-B] Cohort re-run → `reports/cohort-022-phase-b` + judge-batch
- [ ] T032 [US-B] `check_phase_gate.py --phase B` (cumulative floor 5)
- [ ] T033 [US-B] Update `research.md` with A+B delta vs baseline

**Checkpoint**: 0436 or 0495 VA ≥ 0.5; cumulative outcome_gt0 ≥ 5.

---

## Phase 3: User Story C — Benchmark Binding + Slice Expansion (P2)

**Goal**: YoY/comparison items include FY2024 10-K; align expected_bindings with temporal rebind.  
**Targets**: `0600`, `0536`, `0667`  
**Gate**: **SC-C** — ≥7/26 cumulative; ≤1 macro `temporal_mismatch`

### Implementation

- [x] T034 [US-C] Add `expand_slice_accessions()` in `src/evaluation/reproduction/slice_expansion.py`
- [x] T035 [US-C] When `comparison_mode=yoy` or delta intent needs 2 periods, include prior-year 10-K from issuer snapshot
- [x] T036 [US-C] Wire expansion in repro runner / cohort-debug materialization path
- [ ] T037 [US-C] Audit helper: diff CLI `expected_bindings.accessions` vs rebound accession; emit summary in cohort-debug
- [ ] T038 [P] [US-C] Optional draft changelog `data/benchmarks/custom-judge/drafts/quality-v2.0.1/binding_rebound_changelog.jsonl`
- [ ] T039 [P] [US-C] Update benchmark `expected_bindings` for XOM items superseded by validated rebound (draft bundle only)

### Tests

- [x] T040 [P] [US-C] Unit tests `tests/unit/test_slice_expansion.py` — YoY expands [FY2024, FY2025] accessions when present
- [ ] T041 [P] [US-C] Extend `test_macro_fy_binding.py` — 0600 no `TEMPORAL_MISMATCH` when both filings in slice
- [ ] T042 [P] [US-C] Fixture: multi-accession snapshot with XOM FY2024 + FY2025 10-K

### Cohort gate C

- [ ] T043 [US-C] Cohort re-run → `reports/cohort-022-phase-c` + judge-batch
- [ ] T044 [US-C] `check_phase_gate.py --phase C` (floor 7, temporal_mismatch ≤ 1)
- [ ] T045 [US-C] Record MRR recovery diagnostic (target ≥15/26, non-blocking)

**Checkpoint**: 0600 non-abstaining or VA > 0; temporal_mismatch ≤ 1.

---

## Phase 4: User Story D — HTML/Table Fallback (P2)

**Goal**: Extract GT from narrative HTML tables when XBRL catalog empty after guards.  
**Targets**: abstentions with GT in tables (`0436`, `0449`, `0460`)  
**Gate**: **SC-D** — ≥8/26 cumulative; abstention-like ≤12/26

### Implementation

- [x] T046 [US-D] Add `html_table_fallback.py` with `extract_from_html_tables(evidence, query, temporal_intent) -> HtmlTableExtraction | None`
- [x] T047 [US-D] Table heuristics: equity rollforward, cash flow, balance sheet row labels + FY column match
- [x] T048 [US-D] Wire synthesis: after empty catalog + numeric intent → fallback → structured render or abstain
- [x] T049 [US-D] Chunk-dump guard: max cell count / no full-table paste in answer text
- [x] T050 [P] [US-D] Trace `html_fallback_used` on AgentState

### Tests

- [x] T051 [P] [US-D] Unit tests `tests/unit/test_html_table_fallback.py` — equity rollforward HTML fixture parses FY2025 column
- [ ] T052 [P] [US-D] Regression: ambiguous table → abstain; no answer >500 chars from table path
- [ ] T053 [P] [US-D] Fixture HTML snippets under `tests/fixtures/html_tables/`

### Cohort gate D

- [ ] T054 [US-D] Cohort re-run → `reports/cohort-022-phase-d` + judge-batch
- [ ] T055 [US-D] `check_phase_gate.py --phase D` (floor 8, abstain_max 12)
- [ ] T056 [US-D] Update `research.md`

**Checkpoint**: At least one former abstainer (0436/0449/0460) VA > 0.

---

## Phase 5: User Story E — Segment Graph (P3, deferrable)

**Goal**: Segment-dimension facts for segment revenue questions.  
**Targets**: `0428`, second segment cohort item  
**Gate**: **SC-E** — ≥10/26 cumulative (stretch ≥15 SC-001)

**Defer trigger**: Skip until SC-C gate passes OR operator explicitly waives in `research.md`.

### Implementation

- [x] T057 [US-E] Index segment dimension on XBRL facts in graph build / parsing pipeline
- [x] T058 [US-E] Extend catalog filter: `segment_dimension` match when query names segment
- [x] T059 [US-E] Abstain with explicit reason when consolidated fact would mismatch segment GT
- [x] T060 [P] [US-E] Document segment graph asset requirements for CI (may skip heavy graph in unit-only CI)

### Tests

- [x] T061 [P] [US-E] Unit tests `tests/unit/test_segment_catalog.py` — 0428 fixture selects Energy Products revenue
- [ ] T062 [P] [US-E] Fixture `tests/fixtures/segment/0428_xbrl_segment.json`

### Cohort gate E

- [ ] T063 [US-E] Cohort re-run → `reports/cohort-022-phase-e` + judge-batch
- [ ] T064 [US-E] `check_phase_gate.py --phase E` (floor 10, stretch 15)
- [ ] T065 [US-E] Final ladder summary in `research.md`; mean outcome_score vs SC-R (≥0.15)

**Checkpoint**: 0428 VA > 0 or explicit segment abstain with correct reason; cumulative ≥10.

---

## Phase 6: Polish & Documentation

- [x] T066 [P] Unit test `tests/unit/test_check_phase_gate.py` for `phase_gate.evaluate_phase_gate` thresholds
- [ ] T067 Update `specs/022-outcome-score-ladder/checklists/requirements.md` — mark complete after review
- [ ] T068 [P] Cross-link 021 quickstart → 022 ladder in `docs/research-reproduction.md` (one paragraph)
- [ ] T069 Run full pytest suite for 022-touched modules before merge (29 phase tests + 19 related passing)

---

## Dependencies

```text
T001–T004 → T005–T020 (A) → T021–T033 (B) → T034–T045 (C) → T046–T056 (D) → T057–T065 (E)
```

Phases B–E depend on prior phase cohort gate unless waived.

## Parallel opportunities

- T013–T017 (A tests) parallel after T005–T010
- T027–T030 (B tests) parallel after T021–T025
- Contract schemas (T004) parallel with T001

## Validation summary

| Phase | Unit tests | Cohort output | Gate floor |
|-------|------------|---------------|------------|
| A | ratio_pair, guards, computation | `cohort-022-phase-a` | ≥2 outcome>0 |
| B | point_fact_selection | `cohort-022-phase-b` | ≥5 cumulative |
| C | slice_expansion, macro | `cohort-022-phase-c` | ≥7 cumulative |
| D | html_table_fallback | `cohort-022-phase-d` | ≥8 cumulative |
| E | segment_catalog | `cohort-022-phase-e` | ≥10 cumulative |

**Do not use `--replay-input`** for phase validation — always fresh agent re-run.
