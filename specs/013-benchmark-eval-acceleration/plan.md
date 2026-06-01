# Implementation Plan: Benchmark Evaluation Acceleration

**Branch**: `013-benchmark-eval-acceleration` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-benchmark-eval-acceleration/spec.md` — deferred judging (option B), per-item graph slices (option C), resumable full repro. Depends on 012 (merged), 010, 011.

## Summary

Accelerate paper-v1.0 reproduction (~200 items × 5 variants) by (1) **decoupling Gemini judging** from per-item agent execution with a restartable judge-batch phase, (2) **loading only issuer graph snapshots** referenced in each item's `expected_bindings` instead of the full 20-issuer composite for every query, and (3) **variant-level resume**, atomic checkpoints, and recovery subcommands (`judge-batch`, `export-only`). Extends `ReproRunner`, `snapshot_loader`, `QueryService` defer guard, and `agent-query repro` CLI; updates `docs/research-reproduction.md`.

## Technical Context

**Language/Version**: Python 3.12+ (`pyproject.toml`)

**Primary Dependencies**: Existing 012 stack — `ReproRunner`, `CustomJudgeDataset`, `InMemoryGraphQueryAPI`, `QueryService`, `GeminiJudgePanel`, `FlatChunkBaseline`, MLflow tracing, `evaluation.generation.api_retry`

**Storage**:
- Per-variant `reports/repro-{tag}/{variant_id}/results.json` (checkpointed, atomic writes)
- Extended `reports/repro-{tag}/repro_run.json`
- No new LFS artifacts

**Testing**: pytest — unit (accession index, slice load, defer metadata, judge-batch idempotency, atomic write); integration (20-item defer smoke, 5-item resume, single-issuer node count); optional benchmark script for 25% speedup claim

**Target Platform**: Local CLI batch (`agent-query repro`); CI with mocks for defer + resume paths

**Project Type**: Evaluation-layer extensions + minimal retrieval metadata gate

**Performance Goals**:
- Generation phase: zero judge API calls per item when defer enabled (SC-001)
- Per-item graph-full: ≥25% median time reduction vs composite on 10-item smoke (SC-003)
- Full paper-v1.0 wall-clock: materially reduced vs 012 baseline (operator-measured; not a hard gate)

**Constraints**:
- `OFFLINE_BENCHMARK=1` unchanged
- Production `ask` path unchanged when defer not set + no `benchmark_item` metadata
- Relevance materialize still uses full composite (`load_bundle_snapshot`)
- Live judge criteria unchanged (010); only scheduling changes

**Scale/Scope**: 200 items × 5 variants; judge concurrency default 2

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Data Integrity & Grounding** | Slice loads only manifest-listed snapshots; fail-fast on missing accessions; no silent corpus fallback | **PASS** — FR-008/009; item-subgraph contract |
| **II. Structural Semantics Preservation** | No re-parse; uses frozen bundle graphml | **PASS** — selection only |
| **III. Traceability** | Generation still logs MLflow trajectories; defer stores snapshot for judge | **PASS** — FR-005; R3 |
| **IV. Separation of Concerns** | Judge batch in `evaluation/reproduction/`; defer via metadata + repro guard in `QueryService` | **PASS** — R9 guard; no eval logic in graph builder |
| **V. Code Health & Environment Stability** | Pydantic extensions (`ReproRun`, `BenchmarkResult`, `AccessionIndex`); `uv` | **PASS** — data-model.md |
| **VI. Rigorous Agent Evaluation** | Same judge criteria; modular repro flags; audit excludes pending | **PASS** — defer-judge contract |

**Post-design re-check**: Phase 1 contracts preserve boundaries. **Minor retrieval change**: `QueryService` skips audit when repro defer metadata set — documented below; does not weaken 010 production audit on `ask`.

## Project Structure

### Documentation (this feature)

```text
specs/013-benchmark-eval-acceleration/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 entities
├── quickstart.md        # Operator guide (defer, slice, resume)
├── contracts/
│   ├── defer-judge.md
│   ├── item-subgraph.md
│   └── repro-resume-cli.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   └── evaluation.py              # EXTEND: JudgeStatus.PENDING
├── models/
│   └── reproduction.py            # EXTEND: ReproRun checkpoint fields
├── evaluation/
│   └── reproduction/
│       ├── accession_index.py     # NEW: build accession → issuer map
│       ├── snapshot_loader.py     # EXTEND: load_item_subgraph, keep load_bundle_snapshot
│       ├── judge_batch.py         # NEW: batch judge + concurrency
│       ├── runner.py              # EXTEND: defer, slice per item, variant resume, atomic IO
│       └── export.py              # EXTEND: exclude pending judge; export-only path
├── retrieval/
│   └── service.py                 # EXTEND: defer_judge guard, skip run_post_query_audit
├── cli/
│   └── commands/
│       └── repro.py               # EXTEND: flags, judge-batch, export-tables impl

docs/
└── research-reproduction.md       # UPDATE: recovery playbook, defer flags

tests/
├── unit/test_accession_index.py
├── unit/test_item_subgraph.py
├── unit/test_defer_judge.py
├── unit/test_judge_batch_resume.py
├── unit/test_repro_atomic_write.py
└── integration/test_repro_acceleration_smoke.py
```

**Structure Decision**: Single-project CLI; all new logic under `evaluation/reproduction/` except guarded `QueryService` metadata check.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `QueryService` conditional skip of `run_post_query_audit` | Defer judge must not call Gemini inside `answer()` | Duplicate eval-only query path would fork MLflow + graph invoke |
| `benchmark_item` metadata guard | Prevent `REPRO_DEFER_JUDGE=1` from disabling audit on interactive ask | Env-only defer too easy to mis-set during dev |

## Phase 0: Research

Completed in [research.md](./research.md) — decisions R1–R9 (defer control, judge batch, trajectory payload, accession index, cache, resume, export gating, concurrency, constitution guard).

## Phase 1: Design

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Defer judge contract | [contracts/defer-judge.md](./contracts/defer-judge.md) |
| Item subgraph contract | [contracts/item-subgraph.md](./contracts/item-subgraph.md) |
| Resume CLI contract | [contracts/repro-resume-cli.md](./contracts/repro-resume-cli.md) |
| Operator quickstart | [quickstart.md](./quickstart.md) |

## Implementation phases (for /speckit-tasks)

### Phase A — Deferred judging

1. `JudgeStatus.PENDING` + `BenchmarkResult.trajectory_snapshot`
2. `QueryService` defer guard + pending response
3. `ReproRunner` generation path without inline judge; flat-chunk defer
4. `judge_batch.py` + CLI `judge-batch` + `run-all --judge-only`
5. Export gating + tests SC-001/002

### Phase B — Per-item subgraph

1. `accession_index.py` + tests
2. `load_item_subgraph` + slice cache in runner
3. Per-item `InMemoryGraphQueryAPI` + progress logging
4. Flat-chunk slice alignment
5. Integration tests SC-003/004

### Phase C — Resume & recovery

1. Extended `ReproRun` + atomic `repro_run.json` updates
2. Variant-level skip logic
3. CLI `--resume` / `--no-resume` / `--export-only`
4. `export-tables` implementation
5. `docs/research-reproduction.md` playbook
6. Integration tests SC-005/006/007

## Phase 2

Task breakdown: run `/speckit-tasks` (not created by this command).
