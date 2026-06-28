# Feature Specification: Outcome Score Ladder (022)

**Feature Branch**: `019-agent-failure-investigation` (spec `022-outcome-score-ladder`)

**Created**: 2026-06-24

**Status**: Draft — superseded in intent by `023-capability-realignment` (022 heuristic paths)

**Depends on**: `021-xbrl-numeric-binding` (shipped), informal `022` binding/guards commit (`99e9d48`)

**Baseline**: Cohort re-run `reports/cohort-xbrl-022-debug` — **0/26** `outcome_score > 0`, mean VA **0.0**, 18 abstentions, 8 wrong substantive. Calendar rebind to `…-26-000045` on 21/26 XOM items; upstream routing/retrieval improved but **value_alignment unchanged**.

**North star**: Raise `outcome_score` (= `value_alignment` for answer-GT items) on `xbrl_numeric_cohort.json` through iterative agent skills + benchmark alignment, with **validated cohort gates after each phase**.

---

## Problem Statement

`outcome_score` only moves when the judge assigns **value_alignment > 0** (numeric GT within ±5% → VA ≥ 0.5). Improvements to routing, retrieval fidelity, or abstention quality do **not** change the headline metric. The cohort has **14 percent/ratio GTs** and **12 dollar point GTs**; current answers are either abstentions or wrong-concept single-fact numerics.

---

## User Scenarios & Testing

### User Story A — Ratio Pipeline (P1) · Phase 022b

**Goal**: Margin, effective tax rate, and dividend payout questions produce **percent answers from two matched XBRL facts**, not single-fact dollar dumps.

**Target items**: `0548`, `0667`, `0666`, `0592` (+ ratio cohort broadly)

**Why first**: Highest ROI; 9 ratio items; guards alone do not move outcome — pairs + percent output do.

**Acceptance**:

1. **Given** “net profit margin FY2025”, **When** synthesis runs, **Then** answer is `NN.N%` from NetIncome ÷ Revenue (or abstains if pair missing).
2. **Given** “effective tax rate”, **When** catalog has tax expense + pretax income, **Then** ratio uses those concepts—not `IncomeTaxReconciliation*Statutory*` or `AccruedIncomeTaxes*`.
3. **Given** single fact only, **When** ratio intent classified, **Then** structured payload `abstain=true`—no “rate was $8.67 billion”.
4. **Given** fixture pair for margin, **When** `compute_numeric_answer` runs, **Then** output within ±2% of fixture GT.

**Phase gate (cohort)**: `outcome_score > 0` on **≥2** items (expected 2–6); **zero** answers matching `was $.* billion.*(margin|rate|payout)`.

---

### User Story B — Point-Fact Catalog on Rebinding Filing (P1)

**Goal**: After calendar-year rebind to Dec-2025 10-K (`0000034088-26-000045`), extract **primary annual concepts** for equity, cash, and assets at correct scale.

**Target items**: `0436`, `0495`, `0534`, `0547`, `0495` (CAT), point-value cohort

**Acceptance**:

1. **Given** “total shareholder equity FY2025” on XOM slice, **When** catalog builds, **Then** preferred concept is `StockholdersEquity*` annual—not `StockholdersEquityOther`, not Q1 2026 interim.
2. **Given** CAT item `0495`, **When** temporal intent + issuer binding run, **Then** evidence accession matches CAT FY2025 10-K (not XOM).
3. **Given** parsed value within ±5% of GT, **When** judge runs, **Then** `value_alignment ≥ 0.5` (counts toward outcome).

**Phase gate (cumulative)**: **≥5/26** `outcome_score > 0` (expected 5–11 after A+B).

---

### User Story C — Benchmark Binding + Slice Expansion (P2)

**Goal**: Align benchmark `expected_bindings` and repro slice materialization with temporal rebind; include **comparison-year 10-K** in slice for YoY/delta items.

**Target items**: `0600`, `0536`, multi-filing compute items; MRR/relevance realignment

**Acceptance**:

1. **Given** YoY item needing FY2024 + FY2025, **When** slice materializes, **Then** manifest includes both annual 10-K accessions (no `temporal_mismatch` macro fail when corpus has both).
2. **Given** CLI pre-bind accession superseded by temporal rebind, **When** cohort-debug summary builds, **Then** `expected_bindings` audit documents rebound accession (or benchmark updated).
3. **Given** rebinding changes accession, **When** relevance sidecar updated, **Then** MRR on cohort recovers to ≥15/26 (diagnostic, not outcome).

**Phase gate (cumulative)**: **≥7/26** `outcome_score > 0`; **≤1** macro `temporal_mismatch` on cohort; first realistic path to SC-001 (≥15/26) when combined with D/E.

---

### User Story D — HTML/Table Fallback (P2)

**Goal**: When XBRL catalog is empty after guards, extract numeric GT from **narrative HTML tables** in bound filing (MD&A, financial statements).

**Target**: Abstentions with GT present in HTML (equity rollforward, cash flow, segment tables)

**Acceptance**:

1. **Given** empty XBRL catalog for equity question, **When** fallback runs on bound 10-K HTML evidence, **Then** candidate row values parsed with period label.
2. **Given** fallback value within ±5% GT, **When** judge runs, **Then** VA ≥ 0.5.
3. **Given** ambiguous table, **When** fallback runs, **Then** abstain—no HTML chunk dump.

**Phase gate (cumulative)**: **≥8/26** `outcome_score > 0`; abstention-like **≤12/26**.

---

### User Story E — Segment Graph (P3, deferrable)

**Goal**: Segment-dimension XBRL/HTML facts reachable for segment revenue questions.

**Target items**: `0428`, second segment item in cohort

**Acceptance**:

1. **Given** “Energy Products segment revenue 2025”, **When** graph indexes segment dimension, **Then** catalog includes segment-tagged facts or abstains with explicit “no segment fact”.
2. **Given** segment fact matching GT within ±5%, **When** judge runs, **Then** VA ≥ 0.5.

**Phase gate (cumulative)**: **≥10/26** `outcome_score > 0`; SC-001 (≥15/26) achievable with A–E complete.

---

## Requirements

### Functional

- **FR-A1**: Ratio metrics MUST require **two catalog entries** (numerator + denominator) before non-abstaining synthesis.
- **FR-A2**: Ratio/tax/margin answers MUST render as **percent** (`NN.N%`), never bare dollar for rate/margin/payout intents.
- **FR-A3**: Concept guards MUST reject reconciliation/statutory tax lines, `EquityOther`, `OtherAssetsFairValue*` for equity questions.
- **FR-B1**: Point catalog MUST prefer **annual** primary concepts on calendar-rebound filing.
- **FR-B2**: Issuer-aware binding MUST resolve CAT vs XOM accessions from benchmark + temporal intent.
- **FR-C1**: `load_item_subgraph` MUST expand accessions when temporal intent requires comparison-year filings present in issuer snapshot.
- **FR-C2**: Benchmark draft MAY update `expected_bindings.accessions` to match validated rebound accession (documented in override changelog).
- **FR-D1**: HTML fallback MUST only activate when XBRL catalog empty and question is numeric point/ratio.
- **FR-E1**: Graph builder MUST ingest segment dimension on XBRL facts where available; catalog filter MUST prefer segment match.

### Success Criteria (program-level)

| ID | Criterion | After phase |
|----|-----------|-------------|
| **SC-A** | ≥2/26 outcome > 0 | A |
| **SC-B** | ≥5/26 outcome > 0 | A+B |
| **SC-C** | ≥7/26 outcome > 0; ≤1 temporal_mismatch | A+B+C |
| **SC-D** | ≥8/26 outcome > 0; abstentions ≤12 | A+B+C+D |
| **SC-E** | ≥10/26 outcome > 0 (stretch ≥15) | A–E |
| **SC-R** | Mean outcome_score ≥ 0.15 | Full ladder |

### Out of Scope

- Replacing Gemini judge or rubric
- Full 200×5 paper-v1.1 repro
- Publishing v2.0.1 bundle (may draft binding fixes in quality-v2.0.1 draft only)
- Live deterministic `_try_synthesize_*` handlers (Principle VII)

### Assumptions

- Cohort fixture: `specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json` (26 items).
- Judge v3.1 VA rubric: ±2% → 1.0, ±5% → 0.5, else 0.0; abstention → 0.0.
- Phase validation uses **fresh agent re-run** (not `--replay-input`) + `judge-batch --force-rescore`.
