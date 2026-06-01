# Research: Benchmark Evaluation Acceleration (013)

**Feature**: 013-benchmark-eval-acceleration | **Date**: 2026-06-01

## R1 — Deferred judging control surface

**Decision**: Dual control via `REPRO_DEFER_JUDGE=1` environment variable and CLI `--defer-judge` on `repro run`, `repro run-all`, and `repro run` (variant). Propagate into `QueryRequest.metadata["defer_judge"]="true"` and `ReproRunner` flat-chunk path. `QueryService.answer` skips `run_post_query_audit` when metadata or env indicates defer; returns `judge_status=pending` and persists trajectory snapshot fields needed for batch judge.

**Rationale**: Operators already use env flags (`OFFLINE_BENCHMARK`, `USE_MOCK_JUDGE`); CLI mirrors for one-shot runs. Metadata keeps reproduction explicit without changing default `ask` behavior.

**Alternatives considered**:
- Separate `QueryService` subclass in evaluation — rejected: duplicates graph build and MLflow wiring.
- Global monkeypatch of `run_post_query_audit` — rejected: brittle, violates layer boundaries.

---

## R2 — Judge batch phase placement and recovery

**Decision**: Default **after each variant** completes generation (all items have answers, judge pending). Subcommand `repro judge-batch --output DIR [--variant ID] [--concurrency N]`. `run-all --judge-only` skips agent generation and runs batch judge for variants with pending items. Idempotency: skip items where `judge_status` is `ok`, `degraded`, or `not_evaluable` (final states).

**Rationale**: Partial variant tables possible mid-repro; aligns with variant-level resume. Matches user story SC-B03 restart semantics.

**Alternatives considered**:
- Single judge batch after all five variants — rejected as default (no partial variant metrics); support via `--judge-batch-after all` flag optional in implementation.

---

## R3 — Trajectory payload for deferred judge

**Decision**: Extend `BenchmarkResult` with optional `trajectory_snapshot: dict` (serialized `AgentTrajectorySnapshot` from 010) and `generation_mlflow_run_id`. Graph path: capture from `QueryService` response / `build_agent_trajectory_snapshot` before skipping audit. Flat-chunk: build minimal trajectory from citations (existing pattern). Batch judge calls `GeminiJudgePanel.judge(item, answer, trajectory)` with same contract as `ReproRunner._score_*` today.

**Rationale**: Avoid re-invoking LangGraph; judge inputs identical to production audit path.

**Alternatives considered**:
- Re-read trajectory from MLflow only — rejected: adds MLflow dependency in batch phase and fails if run incomplete.

---

## R4 — Per-item subgraph indexing

**Decision**: At `ReproRunner` init (once per repro session), build `AccessionIndex` from bundle `manifest.json` `corpus_bundle.issuer_snapshots` plus `sampling_manifest.json` (if present) mapping each accession → `(ticker, snapshot_id)`. New `load_item_subgraph(bundle_root, accessions: list[str]) -> (slice_id, GraphSnapshot)` in `snapshot_loader.py` reuses `_merge_snapshots` with slice id `slice-{hash(sorted accessions)}`. Empty `expected_bindings.accessions` → `ValueError` with `item_id` (fail fast for paper-v1.0).

**Rationale**: 012 already merges per-issuer snapshots; only selection logic changes. Relevance materialize continues `load_bundle_snapshot` (full composite).

**Alternatives considered**:
- Filter composite in memory — rejected: still pays load/parse cost for 20 issuers every item.
- Single-issuer items load one file only — accepted as primary win.

---

## R5 — In-memory snapshot cache

**Decision**: `ReproRunner` holds `dict[frozenset[str], GraphSnapshot]` keyed by sorted accession tuple (or ticker set). Log cache hit vs load on progress line.

**Rationale**: Dev split has repeated tickers; avoids disk I/O for consecutive items.

**Alternatives considered**:
- LRU across process — deferred; simple dict sufficient for 200-item sequential runs.

---

## R6 — Variant-level and run-level resume

**Decision**: Extend `ReproRun` model with `current_variant`, `items_completed: dict[str, int]`, `completed_variants: list[str]`, `judge_phase_status`, `last_error`. `run_all` loads existing `repro_run.json` when `--resume` (default true). Variant skip when `results.json` length == planned items AND no `judge_status=pending` (if defer) OR all judged (if not defer). Item skip unchanged from 012. Atomic writes: `results.json.tmp` → rename; same for `repro_run.json`. `--no-resume` documents: delete `output_dir` or per-variant subdirs.

**Rationale**: 012 has item-level resume only; operators need variant skip after overnight partial runs.

**Alternatives considered**:
- SQLite checkpoint DB — rejected: JSON artifacts already established in 012.

---

## R7 — Export gating with pending judge

**Decision**: `export_paper_tables` accepts `exclude_pending_judge: bool = True`; audit rows count `judge_status=pending`. `run-all` calls export only when no pending judges OR `--allow-pending-export` for partial reports. Standalone `repro export-tables --input DIR` implements FR-016 (replace 012 stub).

**Rationale**: SC-007 partial export; prevents misleading headline numbers.

---

## R8 — Judge batch concurrency and retries

**Decision**: Reuse `evaluation.generation.api_retry.with_transient_retry` for Gemini judge HTTP. Thread pool or `asyncio` with `concurrency` default **2** (env `REPRO_JUDGE_CONCURRENCY` override). File updates serialized per variant (lock or single-writer thread).

**Rationale**: Proven retry pattern from custom-judge generation; Gemini-only parallelism safe on single API key.

**Alternatives considered**:
- Process pool — rejected: overkill; GIL acceptable for I/O-bound judge calls.

---

## R9 — QueryService defer hook (constitution)

**Decision**: Skip `run_post_query_audit` only when `defer_judge` metadata true **or** `REPRO_DEFER_JUDGE=1` **and** `benchmark_item` metadata present (repro guard — prevents accidental defer on ad-hoc ask with env set). Document in Complexity Tracking; no new production audit exception.

**Rationale**: Principle IV — evaluation signals repro context; production `ask` unchanged.

**Alternatives considered**:
- Evaluation-only wrapper service — rejected: duplicates `answer()` orchestration.
