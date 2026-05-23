# Implementation Plan: Graph-Native Meso and Micro Navigation

**Branch**: `009-graph-native-meso-micro` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)

**Input**: Replace heuristic meso (flat section scoring) and micro (global chunk scan) with LLM-proposed, validator-approved structural graph walks; emit visit traces with edge types; gold-path eval ≥75% reach without full-graph scan.

## Summary

Introduce **`retrieval/navigation/`** (planner, validator, walker) and refactor **`meso_router`** / **`micro_extractor`** to traverse the materialized disclosure graph using **structural edges only**, scoped to the macro-bound filing set. Each hop is **LLM-proposed** and **deterministically validated** (008 pattern). Meso ranks sections from per-filing document roots; **top 3 sections per filing** feed micro multi-hop extraction to evidence chunks. **Trajectory** adds `navigation_trace.json` and extends 007 console payloads. **Evaluation** adds a committed **gold-path** JSONL fixture + `--gold-path` CLI gate for SC-003/SC-004.

## Technical Context

**Language/Version**: Python 3.12+ | **Package manager**: `uv` + `uv.lock`

**Primary dependencies** (existing): `langgraph`, `langchain-openai`, `pydantic`, `typer`, `mlflow`, `rich`, `networkx` (via graph store)

**Reuse**:

| Module | Role |
|--------|------|
| `graph/edge_catalog.py` | Narrow `AGENT_TRAVERSAL_POLICY` → structural only |
| `graph/query_api.py` | Extend neighbors, edges, navigable counts |
| `graph/reachability.py` | Reference for BFS caps / path helpers |
| `retrieval/orchestration/nodes/meso_router.py` | Replace body with navigation walker |
| `retrieval/orchestration/nodes/micro_extractor.py` | Replace global scan with per-section walks |
| `retrieval/orchestration/trace_payloads.py` | Graph-native meso/micro payloads |
| `retrieval/macro/*` | Unchanged; supplies `filing_set` |
| `tracing/mlflow_langgraph.py` | `log_navigation_trace()` |
| `tracing/console_trace/registry.py` | Stage renderers |
| `evaluation/datasets/finagentbench.py` | `load_gold_path_slice()` |

**New modules**:

| Module | Role |
|--------|------|
| `src/retrieval/navigation/models.py` | `HopProposal`, `NavigationVisit`, `NavigationTraceRecord` |
| `src/retrieval/navigation/validator.py` | Structural + scope + budget checks |
| `src/retrieval/navigation/planner.py` | LLM JSON hop proposals + mock fixtures |
| `src/retrieval/navigation/walker.py` | Meso/micro walk loops |
| `src/retrieval/navigation/budget.py` | Budget state from YAML |
| `configs/graph_navigation.yaml` | Hop/visit caps |
| `src/evaluation/metrics/gold_path.py` | SC-003/SC-004 metrics |
| `tests/fixtures/gold_path/gold_path.jsonl` | ≥40 labeled items |

**Testing**: `pytest` — validator unit (no LLM), walker mock paths, trajectory schema contract, ask integration smoke, gold-path benchmark gate (`USE_MOCK_LLM=1`).

**Performance goals**:

- Validator < 5 ms per hop
- Typical ask: < 40 LLM hop calls (meso + micro combined) at default budgets
- `--trace normal` navigation panel < 15% overhead vs 008 baseline ask

**Constraints**:

- No heuristic fallback in production (FR-013a)
- Validator deterministic; LLM never directly mutates graph state
- Evaluation imports navigation types only via trajectory JSON / metrics inputs

**Scale/Scope**: ~12 source files touched, ~5 new modules, 1 config, 1 fixture JSONL, replaces default meso/micro paths.

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Data Integrity & Grounding** | PASS | Micro output only from walked chunk nodes; no flat-pool fallback; insufficient-evidence when empty |
| **II. Structural Semantics Preservation** | PASS | Traversal uses CONTAINS/FOOTNOTE/REFERENCES/NEXT; no flat-string retrieval path |
| **III. Traceability** | PASS | `navigation_trace.json` with per-hop edge types; 007 console extension ([navigation-trajectory.md](./contracts/navigation-trajectory.md)) |
| **IV. Separation of Concerns** | PASS | Graph API in `graph/`; navigation in `retrieval/navigation/`; metrics in `evaluation/` |
| **V. Code Health & Environment Stability** | PASS | Pydantic models; `uv.lock`; contract tests for layer boundaries |
| **VI. Rigorous Agent Evaluation** | PASS | Gold-path harness; reach + path metrics independent of answer judge |

**Post-design re-check**: Contracts define policy, validator, trajectory, and eval harness — no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/009-graph-native-meso-micro/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── graph-navigation-policy.md
│   ├── hop-proposal-validator.md
│   ├── navigation-trajectory.md
│   └── gold-path-eval-harness.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source (repository root)

```text
src/
├── graph/
│   ├── edge_catalog.py           # AGENT_TRAVERSAL_POLICY := STRUCTURAL only
│   └── query_api.py              # + outgoing_edges, navigable_node_count
├── retrieval/
│   ├── navigation/               # NEW
│   │   ├── models.py
│   │   ├── planner.py
│   │   ├── validator.py
│   │   ├── walker.py
│   │   └── budget.py
│   └── orchestration/
│       ├── nodes/meso_router.py    # graph-native rewrite
│       ├── nodes/micro_extractor.py
│       └── trace_payloads.py
├── tracing/mlflow_langgraph.py   # log_navigation_trace()
├── evaluation/metrics/gold_path.py
└── cli/commands/test.py          # --gold-path flag

configs/graph_navigation.yaml

tests/
├── fixtures/gold_path/gold_path.jsonl
├── fixtures/navigation_planner/
├── unit/test_navigation_*.py
├── contract/test_navigation_trajectory_schema.py
├── contract/test_navigation_layer_boundaries.py
├── integration/test_gold_path_benchmark.py
└── integration/test_ask_navigation_trajectory.py
```

**Structure Decision**: `retrieval/navigation/` mirrors `retrieval/macro/` — testable validator and walker without LangGraph coupling; orchestration nodes remain thin adapters.

## Implementation Phases (for `/speckit-tasks`)

### Phase 1 — Policy, models, graph API

- Narrow `AGENT_TRAVERSAL_POLICY` to `STRUCTURAL_EDGE_TYPES`
- Add `configs/graph_navigation.yaml` + `NavigationBudgetState`
- Pydantic models per [data-model.md](./data-model.md)
- Extend `GraphQueryAPI` (`outgoing_edges`, `document_roots_for_filings`, `navigable_node_count`)

### Phase 2 — Validator, planner, walker

- Implement `validator.py` per [hop-proposal-validator.md](./contracts/hop-proposal-validator.md)
- Implement `planner.py` + mock fixtures (**before** walker)
- Implement `walker.py` (meso from document roots, micro from section roots)
- Extend `SectionCandidate` / `EvidenceChunk` in `models/query.py`
- Unit tests: rejection codes, scope, budgets, structural-only edges

### Phase 3 — Node integration
- Refactor `meso_router` / `micro_extractor` to use walker + planner; top-3 handoff
- Remove global chunk scan as default path; map chunks from visited terminal nodes
- Preserve intent_trace / XBRL fact handling inside graph reachability only

### Phase 4 — Trajectory & console trace

- `log_navigation_trace()` + `TrajectoryRecord` field
- Extend `build_meso_router_trace_payload` / `build_micro_extractor_trace_payload`
- Contract + integration tests (SC-001)

### Phase 5 — Gold-path evaluation

- Author `tests/fixtures/gold_path/gold_path.jsonl` (≥40 items)
- `evaluation/metrics/gold_path.py` + `--gold-path` on `agent-query test`
- CI gate: `chunk_reach_rate >= 0.75` with `USE_MOCK_LLM=1`
- README + [quickstart.md](./quickstart.md)

## Complexity Tracking

No constitution violations requiring justification.
