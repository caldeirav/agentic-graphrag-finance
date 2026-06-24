# Feature Specification: Capability Realignment (023 · 022c)

**Feature Branch**: `019-agent-failure-investigation` (spec `023-capability-realignment`)

**Created**: 2026-06-24

**Status**: Draft

**Depends on**: `022-outcome-score-ladder` (shipped `8e802e7`), `021-xbrl-numeric-binding`, `020-agent-capability-first`, Constitution **Principle VII**

**Supersedes (intent, not deletes history)**: Heuristic-primary paths from 022 phases A–D (`ratio_pair_resolution`, `point_fact_selection`, `html_table_fallback` as live gates)

**Baseline**: `reports/cohort-022-phase-e` — **0/26** `outcome_score > 0`; **0** answers via `computed_numeric`; **19** abstention-like; synthesis fell through to **structured_llm / live_llm** on almost every item. Empty `synthesis_path=` in logs due to missing `trajectory_snapshot` on non-deferred repro runs.

**North star**: Restore **capability-first** numeric synthesis (Principle VII): structured catalog → **LLM disambiguation** → **Python math only** → rendered structured answer or **honest abstention** — **no** live keyword concept routers and **no** numeric fallthrough to narrative LLM on the XBRL cohort.

---

## Problem Statement

022 added deterministic selection layers (regex concept families, point-fact priority tables, HTML row heuristics) to chase `outcome_score`. This **conflicts with Principle VII**, which orders remediation as: structured contracts → prompt metadata → **LLM skills** → cohort gates — not expanding keyword routers.

The cohort proved the heuristic stack **did not work in production** either: `_try_computed_numeric_synthesis` returned `None` on most items, so **structured_llm** and **live_llm** dominated — the same failure mode as pre-022, with **more code** and **0/26** outcomes.

Root causes to address in this feature (not more regex):

1. **Synthesis fallthrough** — computed path abstains → `None` → LLM narrative runs and scores VA 0.
2. **Retrieval gap** — ratio items (e.g. 0548) lack **both** numerator and denominator XBRL chunks in evidence at synthesis time.
3. **LLM skill under-used** — `resolve_xbrl_facts` bypassed by heuristic pair/point selectors and hard catalog pre-filters.
4. **Telemetry gap** — repro cannot verify `synthesis_path` when `defer_judge=False`.

---

## User Scenarios & Testing

### User Story 1 — Single Live Numeric Path (P1)

**Goal**: On answer-GT numeric items, synthesis uses **only** the structured pipeline: catalog → metric intent → XBRL resolution → compute → render **or** abstain. No live_llm / structured_llm fallback for numeric intent.

**Acceptance**:

1. **Given** a numeric financebench question on the cohort, **When** synthesis completes, **Then** `synthesis_path` is `computed_numeric` or `numeric_abstain` — never `live_llm` or `structured_llm`.
2. **Given** ratio intent and insufficient facts in catalog, **When** synthesis runs, **Then** answer is explicit insufficiency with **no** LLM-invented percentage in prose.
3. **Given** `USE_MOCK_LLM=1`, **When** CI runs, **Then** mock deterministic paths remain available (unchanged).

**Gate**: Cohort — **0/26** answers classified as `live_llm_narrative` or `structured_llm` on numeric items (operator script).

---

### User Story 2 — LLM Pair Resolution for Ratios (P1)

**Goal**: Margin, tax rate, and payout ratios select **two** XBRL facts via **extended `resolve_xbrl_facts`** (LLM skill), not `ratio_pair_resolution` regex routing.

**Target items**: `0548`, `0667`, `0666`, `0592`

**Acceptance**:

1. **Given** catalog with tax expense and pretax income, **When** resolution runs for effective tax rate, **Then** trajectory records **two** `selected_chunk_ids` and rationale — no statutory/reconciliation concepts in selection.
2. **Given** two resolved facts, **When** `compute_numeric_answer` runs, **Then** output is `NN.N%` with `formula` and `inputs` populated.
3. **Given** only one matching fact, **When** resolution runs, **Then** skill returns `sufficient=false` and synthesis abstains.

**Gate**: ≥2/26 `outcome_score > 0`; zero forbidden `$ … billion` rate/margin/payout patterns.

---

### User Story 3 — Retrieval Enrichment for Multi-Fact Metrics (P1)

**Goal**: When metric intent requires two facts (ratio, delta, YoY), retrieval/micro stage **must** surface complementary XBRL concepts in evidence before synthesis.

**Target items**: `0548`, `0536`, `0600`, `0667`

**Acceptance**:

1. **Given** margin question and catalog missing revenue **or** net income in current evidence, **When** enrichment runs, **Then** additional XBRL chunks for the missing concept family are added from bound filing(s) before synthesis.
2. **Given** YoY delta intent, **When** slice includes comparison-year 10-K (022-C expansion), **Then** both periods’ facts appear in catalog for resolution.
3. **Given** enrichment cannot find complementary fact, **When** synthesis runs, **Then** abstain — no LLM fallback.

**Gate**: For ratio targets, ≥3/4 items have ≥2 distinct ratio-relevant concepts in catalog at synthesis (trace audit field).

---

### User Story 4 — Post-Selection Validation, Not Pre-Filter Catalog (P2)

**Goal**: Move `xbrl_concept_guards` from **hard catalog exclusion** to **LLM prompt constraints + post-resolution rejection** so the skill sees the full structured catalog.

**Acceptance**:

1. **Given** catalog including reconciliation tax lines, **When** LLM resolution runs for tax rate, **Then** prompt instructs exclusion; if LLM picks invalid concept, **post-validator rejects** and abstains.
2. **Given** equity question, **When** resolution runs, **Then** LLM selects primary annual `StockholdersEquity*` with period match — not pre-filtered to empty catalog.
3. **Given** mock resolution in CI, **When** guards reject pick, **Then** unit test asserts abstain payload.

**Gate**: Abstention-like ≤15/26 (may rise briefly vs wrong substantive); wrong-concept substantive ≤5/26.

---

### User Story 5 — Repro Telemetry (P2)

**Goal**: Cohort-debug logs and `results.json` always include `synthesis_path` and numeric pipeline trace fields.

**Acceptance**:

1. **Given** `defer_judge=False` cohort run, **When** item completes, **Then** `BenchmarkResult.trajectory_snapshot.synthesis_path` is populated.
2. **Given** computed path, **When** trace exported, **Then** optional fields include `metric_intent_json`, `xbrl_resolution_rationale`, `ratio_pair_resolution_json` removed or renamed to `xbrl_resolution_json`.

**Gate**: 26/26 items have non-empty `synthesis_path` in results artifact.

---

### User Story 6 — Heuristic Retirement (P2)

**Goal**: 022 heuristic modules demoted to **mock-only**, tests, or deleted after LLM path passes gates.

**Acceptance**:

1. **Given** live synthesis (`USE_MOCK_LLM` unset), **When** import graph loads, **Then** `ratio_pair_resolution`, `point_fact_selection`, `html_table_fallback` are **not** called from `synthesis.py`.
2. **Given** plan Complexity Tracking, **When** review completes, **Then** each retired heuristic has sunset note or mock-only ADR.
3. **Given** 022 phase E segment filtering, **When** retained, **Then** documented as graph-index concern — not regex synthesis router.

**Gate**: Grep/regression test — no live imports of retired modules from synthesis (allow evaluation/slice_expansion).

---

## Requirements

### Functional

- **FR-001**: Numeric synthesis MUST NOT fall through to `structured_llm` or `live_llm` when `metric_intent.metric_type` ∈ {point, ratio, delta, percent_change}.
- **FR-002**: Ratio metrics MUST use **LLM `resolve_xbrl_facts`** to select **two** chunk ids (or declare insufficient); Python MUST compute percent.
- **FR-003**: `build_xbrl_fact_catalog` MUST include all parseable XBRL entries passing **period/temporal** filter only; concept guards MUST NOT empty catalog in live path.
- **FR-004**: Post-resolution validator MUST reject statutory tax, OCI-as-payout, equity-other, wrong-period picks before emit.
- **FR-005**: Retrieval enrichment MUST add missing ratio/delta concept families from bound filing XBRL when evidence lacks them.
- **FR-006**: `QueryService` / repro runner MUST persist full trajectory snapshot (including `synthesis_path`) on all judge modes.
- **FR-007**: Live path MUST NOT import heuristic selectors from 022 A/B/D; slice expansion (022-C) MAY remain in repro layer.
- **FR-008**: Abstain answers MUST use structured render (`Insufficient evidence: …`) with `QueryStatus.INSUFFICIENT_EVIDENCE` — not narrative LLM explanation.

### Success Criteria

| ID | Criterion | Measurement |
|----|-----------|-------------|
| **SC-001** | ≥2/26 `outcome_score > 0` | Cohort gate (ratio targets) |
| **SC-002** | ≥5/26 cumulative after point fixes | Cohort gate |
| **SC-003** | 0/26 numeric items use live_llm/structured_llm | Answer classifier script |
| **SC-004** | 26/26 non-empty `synthesis_path` in results | Artifact audit |
| **SC-005** | Constitution VII checklist PASS | plan.md Complexity Tracking |
| **SC-006** | Mean VA ≥ 0.10 vs 022-E baseline 0.0 | judge-batch |

### Non-Functional

- **NFR-001**: No new live `_try_synthesize_*` keyword handlers.
- **NFR-002**: MLflow trajectory retains resolution rationale for audit.
- **NFR-003**: Cohort validation uses fresh agent re-run (not `--replay-input`).

---

## Out of Scope

- Replacing Gemini judge or VA rubric
- Full 200×5 paper repro
- Publishing v2.0.1 bundle (binding draft edits still allowed)
- Re-implementing 022 heuristic ladders “better” with more regex
- LLM parsing raw XBRL instance XML (parsing layer owns structure — Principle II/IV)

---

## Assumptions

- Cohort fixture: `specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json` (26 items).
- External LLM available for metric intent and XBRL resolution in cohort runs (same as 022-E).
- Python arithmetic after fact selection remains mandatory (021 decision stands).
- Segment dimension work (022-E) continues via **graph/catalog metadata**, not new synthesis keyword handlers.

---

## Constitution Alignment (Principle VII)

| VII rung | This feature |
|----------|--------------|
| 1 Structured contracts | Keep `StructuredAnswerPayload`; block numeric LLM fallthrough |
| 2 Prompt metadata | Enrich resolution prompt with fiscal labels, metric_type, forbidden concepts |
| 3 LLM skills | **Primary** fact/pair selection via `resolve_xbrl_facts` |
| 4 Cohort gate | Same 26-item fixture; SC-001–SC-006 |

**Retired from live path (022 violations)**: regex pair routing, point priority tables, HTML regex fallback as primary.
