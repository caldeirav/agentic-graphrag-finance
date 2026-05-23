# Research: Autonomous Macro Routing (008)

**Branch**: `008-autonomous-macro-routing` | **Date**: 2026-05-23

## R1: Where binding happens today

**Decision**: Keep **CLI deterministic binding** for explicit `CorpusTemporalScope` flags; move **autonomous NL binding** into **`macro_router`** when the CLI leaves scope unresolved (empty anchor/periods/accessions).

**Rationale**: `corpus_pipeline.py` already calls `bind_filings_for_query()` before `QueryService.answer()`. When scope is empty it currently passes the **full snapshot** as `pre_bound_filings`, which causes `macro_router` to skip LLM (`macro_llm_skipped=True`) and never apply YoY/QoQ pairing (clarification Q3). 008 changes empty-scope asks to pass **`filing_set=[]`** (or a `binding_deferred=True` flag) so macro runs the LLM→validator path.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| All binding in CLI only | Duplicates LLM logic outside LangGraph; breaks trajectory stage model |
| LLM-only macro (no validator) | Violates clarification Q3 and constitution fail-closed |
| New graph node before macro | Extra latency; macro already owns temporal scope in 001 design |

## R2: LLM proposal + deterministic validator

**Decision**: **`MacroBindingProposal`** JSON from LLM (accessions or anchor/comparison hints) → **`validate_macro_binding()`** checks manifest membership, pairing rules (YoY/QoQ), misalignment, CLI precedence → **`FilingBinding`** or **`MacroBindingError`**.

**Rationale**: Matches clarification: LLM proposes, validator approves or fail closed. Validator is unit-testable with stub proposals; benchmarks do not depend on LLM wording.

**Pairing rules encoded in validator** (from clarifications):

| Mode | Rule |
|------|------|
| YoY + quarterly metric cue | Latest 10-Q + same fiscal-quarter 10-Q one year earlier |
| YoY + annual/unspecified | Latest two 10-Ks |
| QoQ | Latest 10-Q + immediately prior 10-Q by `period_end` |
| Single anchor | `resolve_temporal_scope` anchors (latest_quarter, prior_quarter, latest_annual, FY labels) |

**Misalignment default**: Fail closed; narrow only if exactly one valid anchor remains (Q1).

## R3: Phrase catalog vs free-form LLM

**Decision**: Ship **`configs/macro_phrases.yaml`** as **hints** for the LLM system prompt and **post-hoc validator labels**; validator does **not** require phrase match. Optional fast-path: if query matches catalog only (no comparison ambiguity), skip LLM and build proposal deterministically (optimization, must still pass validator).

**Rationale**: English-first v1 per spec; catalog improves consistency without blocking paraphrases. Fast-path keeps CI/mock fast.

## R4: Trajectory and console trace

**Decision**: Extend **`MacroPlan`** / new **`MacroBindingRecord`** in state; log **`macro_binding.json`** MLflow artifact; extend **`build_macro_router_trace_payload`** with `proposal`, `validation`, `binding_source` (`cli` | `llm` | `deterministic`).

**Rationale**: FR-005/FR-008 and constitution III require durable audit; 007 console trace already has `macro_router` stage.

## R5: Evaluation slice

**Decision**: Add **`data/benchmarks/finagentbench/macro_binding.jsonl`** (≥50 items) with `expected_bindings`, `multi_filing_required`, `temporal_scope` for harness; add **`evaluation/metrics/macro_binding_accuracy.py`** and CLI/subcommand or `agent-query test --macro-binding`.

**Rationale**: Clarification Q4; `BenchmarkItem` already has `expected_bindings` and `CorpusTemporalScope` in `models/evaluation.py`. Reuse registry loader pattern from `finagentbench.py`.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| NL-only benchmark cases | 003 contract prohibits; labels must be explicit |
| External FinAgentBench dump only | Not reproducible in CI |

## R6: CLI precedence

**Decision**: Reuse **003 precedence**: explicit CLI scope → deterministic `bind_filings_for_query` → macro **validates and records** (no LLM accession pick). Empty CLI scope → macro autonomous path. Irreconcilable CLI vs LLM proposal → fail before meso.

**Rationale**: FR-006; existing tests in `tests/unit/test_temporal_binding.py`.

## R7: Performance

**Decision**: Target **+1 LLM call** on macro path only when scope not CLI-resolved; validator **< 50 ms** on manifest ≤10 filings. Mock/stub path for CI via `USE_MOCK_LLM` returning fixed proposal JSON.

**Rationale**: Macro already invokes LLM when not pre-bound; feature adds validator CPU only.
