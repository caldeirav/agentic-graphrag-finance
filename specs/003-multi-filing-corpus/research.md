# Research: Multi-Filing Issuer Corpus (003)

**Date**: 2026-05-20 | **Plan**: [plan.md](./plan.md)

## R1: Extend 002 EDGAR listing vs new filing index service

**Decision**: Extend `edgar_client.py` with `list_recent_filings()` using existing `SUBMISSIONS_URL` `filings.recent` arrays (form, accessionNumber, filingDate, reportDate).

**Rationale**: 002 already resolves latest single filing from this payload; listing N recent 10-K/10-Q is a loop + filter with no new credentials or API vendor. Aligns with user directive to extend ingestion, not replace it.

**Alternatives considered**:
- sec-api filing history API — rejected for v1 (extra dependency surface; EDGAR sufficient for cap ≤12)
- Manual accession-only corpus — kept as `CorpusDefinition.explicit_accessions` override

## R2: Multi-filing graph materialization

**Decision**: Reuse `graph.builder.build_snapshot(issuer_id, documents: list[ParsedDocument])` and `graph.store.save_snapshot`; add `graph/registry.py` for issuer-level `index.json`.

**Rationale**: Builder already creates per-filing `doc-{accession}` nodes and `TEMPORAL_TRANSITION` edges between sorted `period_end` dates. 001/002 single-filing CLI path passes `[doc]` only — 003 changes orchestration, not graph semantics.

**Alternatives considered**:
- Separate graph per filing + federation layer — rejected (spec requires unified issuer snapshot with cross-filing linkage)
- Merge GraphML files post-hoc — rejected (loses single manifest, complicates retrieval)

## R3: Fiscal period labeling for temporal scope

**Decision**: Derive display/bind labels from EDGAR `reportDate` + `form_type` on each `FilingRef`; map “prior quarter” / “Q3” to issuer fiscal year-quarter by ordering filings by `period_end` within the active snapshot (clarification A).

**Rationale**: SEC report dates reflect issuer fiscal calendar; calendar-quarter mapping explicitly out of scope unless user passes explicit calendar date range.

**Alternatives considered**:
- LLM-only period inference — rejected as sole mechanism for benchmarks; allowed for CLI NL when no structured flags
- XBRL `dei:DocumentFiscalPeriodFocus` extraction — deferred to Phase 4 enhancement if reportDate granularity insufficient

## R4: Default workflow (materialize then bind)

**Decision**: Pre-materialize default corpus (latest 10-K + 4 trailing 10-Q) on first `ask` or via `agent-query materialize`; per question bind subset; extend snapshot version when required period missing (clarification C).

**Rationale**: Matches spec FR-008a; avoids full lazy per-question fetch while keeping query-time work small.

**Alternatives considered**:
- Eager-only without query subset — rejected (re-materializes unnecessarily)
- Lazy-only — rejected (no standing snapshot for repeat queries)

## R5: Corpus overflow and stale snapshots

**Decision**: Reject materialization when definition &gt; cap (clarification B); on ask with older snapshot, warn + list newer EDGAR filings without blocking (clarification C).

**Rationale**: Fail-closed on silent truncation; analyst control on refresh vs exploratory reuse.

## R6: Benchmark vs CLI temporal input

**Decision**: Benchmarks use structured `temporal_scope` JSON only; CLI supports NL + optional flags with explicit override (clarification D).

**Rationale**: Reproducible binding assertions (FR-017); CLI usability preserved.
