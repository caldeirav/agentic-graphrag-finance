# Research: Reproduction Evaluation Validity & Stratified Ablations (015)

**Feature**: 015-repro-eval-validity | **Date**: 2026-06-06

## R1 — Evidence stratum classification

**Decision**: Assign `primary_evidence_source` using the uniform all-or-mixed rule on `relevant_chunk_ids`: classify each chunk id as `html` or `xbrl` via substring heuristics aligned with `walker.py` (`html-` in id → html; `xbrl` in id or `CHUNK_XBRL` pattern → xbrl); if all html → `html`, all xbrl → `xbrl`, both types → `mixed`, empty list → `unknown`.

**Rationale**: Matches clarified spec rule and existing graph node id conventions (`doc-{accession}-html-{section}`, `doc-{accession}-xbrl-{hash}`). No manual per-item tags required for v1.

**Alternatives considered**:
- Majority vote across chunk types — rejected: contradicts clarification session answer.
- Inspiration profile heuristics (finder vs financebench) — rejected: confounds profile with evidence modality.
- Graph node index lookup — rejected: adds corpus dependency at export time; substring rule is sufficient for labeled chunk ids.

---

## R2 — Re-judge resume gate

**Decision**: `judge-batch` skips an item when `judge_verdict.judge_version >= "v2"` (lexicographic version compare on numeric suffix) **and** normalized trajectory has non-empty `evidence_chunks` after `normalize_trajectory_state`. Items with empty evidence but non-empty answer citations remain pending (citation fallback still applies). Add optional `--force-rescore` to bypass skip for operator overrides.

**Rationale**: Idempotent re-score of paper-v1.0 after P0 merge without redundant Gemini calls; edge case from spec (old checkpoints with citations but no snapshot evidence) still re-scores.

**Alternatives considered**:
- Always re-judge all items — rejected: expensive and unnecessary once v2 scores exist.
- Skip on any `judge_status=ok` — rejected: would skip pre-P0 incorrect scores.

---

## R3 — Structural metrics extraction

**Decision**: After each variant completes, derive per-item `used_accessions` from trajectory `filing_set` / `document_route` accessions and citation chunk node ids (parse accession from `doc-{accession}-...` prefix); derive `visited_paths` from `graph_traversal` node ids and section path fields. Call existing `aggregate_structural_metrics()` and persist on `EvalRunRef.structural_metrics` in `repro_run.json`.

**Rationale**: `structural.py` already implements 012 binding/section/multi-filing logic; runner currently leaves zeros. Extraction reuses persisted trajectory snapshots without re-running agents.

**Alternatives considered**:
- Compute only for graph-full — rejected: clarification requires all five variants.
- Re-parse MLflow traces at export time — rejected: checkpoints already store `trajectory_snapshot`.

---

## R4 — Investigation note aggregation

**Decision**: Replace per-item anomaly emission in `detect_run_anomalies` with pattern keys `(severity, variant_id, pattern_code)` and aggregate counts + up to 5 example `item_id`s. Known ablation patterns (`ABLATION_ZERO_CITATIONS`, `ABLATION_ZERO_RANKING`) emit one info note per variant. Cap rendered top-level notes at 25 (merge lowest-severity duplicates if needed).

**Rationale**: paper-v1.0 produced 527 notes (393 zero-citation warnings); aggregation restores operator signal without losing drill-down via examples.

**Alternatives considered**:
- Pagination only — rejected: still generates huge DOM and misses SC-004.
- Remove per-item checks entirely — rejected: graph-full unexpected issues must still surface.

---

## R5 — "Outcome exceeds graph-full" guard

**Decision**: Emit cross-variant outcome inversion note only when comparison variant has `mrr > 0` or `citation_count > 0` on at least one item in the comparison (aggregate check per variant, not per-item headline row alone).

**Rationale**: Abstaining ablations with high outcome from pre-P0 judge bugs showed zero retrieval overlap; warning was noise after fix and misled operators.

**Alternatives considered**:
- Remove outcome comparison notes entirely — rejected: still useful for flat-chunk regressions with real citations.

---

## R6 — Stratified export schema

**Decision**: Add `tables/by_evidence_source.csv` (columns: variant, stratum, metric, value, item_count, abstention_rate, exclusion fields) and `tables/variant_delta_by_source.csv` (adds `primary_evidence_source`). Exclude `unknown` stratum from aggregates; record excluded count in `export_manifest.json`. Low-n strata (< 10 items) included with `na_reason=low_n` on delta rows.

**Rationale**: Satisfies FR-013/FR-014 without breaking existing pooled `variant_delta.csv` consumers (014 report, paper pipeline).

**Alternatives considered**:
- Embed strata as extra columns on `headline.csv` — rejected: breaks 012 schema and complicates pivot tables.
- Single wide CSV per stratum file — rejected: harder to join with existing export code.

---

## R7 — Abstention rate definition

**Decision**: Per variant and stratum, `abstention_rate = (# headline-eligible items with abstention answer) / (# headline-eligible items in stratum)`. Abstention = empty citations and answer text matching abstention patterns (reuse `outcome_scoring.is_abstention`).

**Rationale**: First-class metric for ablation interpretability (SC-006: no-walker ≥ 80% on HTML stratum).

**Alternatives considered**:
- Include non-eligible items — rejected: inconsistent with headline exclusion rules.

---

## R8 — Synthesis grounding (agent quality)

**Decision**: Document FR-006 as agent prompt + validation guidance in reproduction docs; add optional post-answer lint in eval runner that flags numeric tokens in answer not present in cited chunk text (warning artifact, not hard fail in v1).

**Rationale**: Full synthesis rewrite is out of scope for checkpoint re-score; smoke runs can catch regressions without blocking export.

**Alternatives considered**:
- New judge criterion only — rejected: does not prevent invention at generation time.
