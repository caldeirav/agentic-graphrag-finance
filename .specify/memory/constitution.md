<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Modified principles:
  - IV. Strict Separation of Concerns → redefined layer model (agentic retrieval unified;
    evaluation as independent layer)
  - III. Traceability → MLflow as required trajectory store for eval consumption
- Added principles: VI. Rigorous Agent Evaluation (NON-NEGOTIABLE)
- Removed sections: None (retired separate `agent/` production layer)
- Templates: plan-template.md ✅ | spec-template.md ✅ | tasks-template.md ✅
- Follow-up TODOs: None
-->

# Agentic GraphRAG Finance Constitution

## Core Principles

### I. Data Integrity & Grounding (NON-NEGOTIABLE)

All outputs, extractions, and derived metrics MUST be verifiably grounded in raw SEC
source data (filings, exhibits, and authoritative EDGAR artifacts). The system MUST
NOT invent figures, entities, filing references, or narrative claims absent from source
material.

Hallucinated content and mathematical or parsing errors in numeric extraction are
**catastrophic failure states**. Any pipeline stage that cannot prove grounding MUST
fail closed (reject, flag, or halt) rather than emit unverified data.

**Rationale**: Financial AI errors propagate into compliance, investment, and audit
decisions; ungrounded outputs are indistinguishable from fraud at scale.

### II. Structural Semantics Preservation (NON-NEGOTIABLE)

Financial documents MUST NOT be reduced to undifferentiated flat strings for indexing
or retrieval. Parsing architectures MUST preserve:

- Table layouts (rows, columns, headers, merged cells where applicable)
- Nested footnotes and cross-references
- Tabular–textual hierarchy (statements, schedules, MD&A blocks, and their containment)

Downstream graph and agentic retrieval layers MUST consume structured representations
that retain these semantics; lossy flattening is permitted only behind explicit,
versioned transformation contracts with documented invariants.

**Rationale**: SEC filings encode meaning in structure; destroying layout corrupts
ratio math, period alignment, and footnote linkage.

### III. Traceability (NON-NEGOTIABLE)

Every analytical decision during agentic retrieval MUST emit a durable trajectory record
suitable for audit and benchmarking. Each record MUST capture, at minimum:

- **Plan**: intent, steps considered, and rationale for the chosen path
- **Document route**: filing identifiers, sections, and navigation path through the corpus
- **Graph traversal**: node and edge identifiers visited (with types)
- **Evidence**: exact extracted chunk(s) (content hash or stable pointer) used to support conclusions

Trajectories MUST be logged to **MLflow** (or a successor store under an explicit
migration contract) so the evaluation layer can consume runs, parameters, artifacts,
and step-level traces without coupling to production retrieval internals.

Trajectories MUST be machine-readable, correlatable across runs, and retained for
benchmark datasets. Silent reasoning without persisted trace is prohibited for
production analytical paths.

**Rationale**: Regulators, researchers, and engineers require reproducible evidence
chains; trajectory-aware benchmarks are impossible without a stable observability sink.

### IV. Strict Separation of Concerns (NON-NEGOTIABLE)

The system MUST maintain hard boundaries between **four layers**. Agent orchestration
is part of **agentic retrieval**, not a standalone production layer. No layer may
embed responsibilities belonging to another:

| Layer | Responsibility | MUST NOT |
|-------|----------------|----------|
| **Parsing** | Ingest SEC sources; preserve structure; emit validated document objects | Build graphs, run retrieval, score benchmarks, or answer end-user queries |
| **Graph building** | Materialize nodes/edges from parsed artifacts; enforce schemas | Parse raw filings, orchestrate agents, or execute evaluation judges |
| **Agentic retrieval** | Multi-stage lookup over graph and chunks **with integrated agent orchestration** (planning, routing, synthesis); emit MLflow-backed trajectories | Mutate source filings, redefine parse semantics, run external judges, or own benchmark registry logic |
| **Evaluation** | Independently measure agentic retrieval: final **accuracy** on benchmark tasks **and** intermediate decision quality via trajectories; invoke **external judge models**; orchestrate modular datasets/benchmarks | Implement retrieval logic, parse filings, or mutate production graph/chunk stores |

Cross-layer integration occurs only through typed interfaces and explicit events.
Shared mutable state across layers is forbidden except via defined stores (e.g.,
graph DB, chunk store, MLflow tracking server).

The evaluation layer MUST remain deployable and runnable without importing agentic
retrieval internals beyond published contracts (inputs, outputs, trajectory handles).

**Rationale**: Unified agentic retrieval reflects how the system actually operates;
an independent evaluation layer prevents training-on-the-test-set coupling and
enables rigorous comparison of agent strategies.

### V. Code Health & Environment Stability (NON-NEGOTIABLE)

**Typing**: Data contracts MUST use strong static typing end-to-end. Graph node and
edge schemas, parser outputs, chunk references, trajectory payloads, and evaluation
run manifests MUST be defined as explicit types (e.g., Pydantic models, TypedDicts,
or equivalent) with validation at boundaries. Untyped `dict`/`Any` crossing layer
boundaries is prohibited except in narrowly scoped adapter shims covered by tests.

**Tooling**: All Python virtual environments, dependency resolution, and package
management MUST be performed exclusively with **`uv`**. Lockfiles (`uv.lock`) MUST
be committed; builds MUST be reproducible from lock alone. Alternative env managers
(`pip`, `poetry`, `conda`, `pipenv`) MUST NOT be used in this repository.

**Rationale**: Financial graph systems fail silently on schema drift; deterministic
builds prevent "works on my machine" regressions during audit reproduction.

### VI. Rigorous Agent Evaluation (NON-NEGOTIABLE)

The project MUST continuously measure the effectiveness of the **agentic retrieval**
approach using state-of-the-art financial datasets and benchmarks. Evaluation MUST
cover both:

1. **Outcome accuracy** — final answers vs. benchmark ground truth (or accepted rubrics)
2. **Process quality** — intermediate decision-making scored from MLflow trajectories
   via an **external judge model** (independent from the retrieval agent)

The evaluation layer MUST be **modular**:

- **Dataset registry**: plug-in adapters for financial QA, extraction, and reasoning
  benchmarks; datasets MUST be addable/removable without changing retrieval code
- **Benchmark registry**: composable benchmark definitions (metrics, splits, judge prompts)
- **Judge abstraction**: swappable external judge models with versioned configuration

Comparisons across agent configurations, retrieval stages, or model versions MUST be
reproducible from locked dependencies, pinned judge versions, and recorded MLflow run IDs.

**Rationale**: Agentic systems fail in subtle ways; outcome-only metrics miss harmful
reasoning paths. Modular benchmarks keep the project aligned with evolving SOTA while
preserving separation from production retrieval.

## System Architecture Constraints

Layer layout MUST map to deployable or testable packages/modules (names illustrative):

- `parsing/` — SEC ingest, structural preservation, validation gates
- `graph/` — schema-driven graph construction and persistence
- `retrieval/` — multi-stage agentic IR (orchestration + synthesis + MLflow trace emission)
- `evaluation/` — benchmark runners, dataset/benchmark plugins, external judge integration

Production code MUST NOT place a separate top-level `agent/` package that duplicates
retrieval orchestration. Agent modules live **inside** `retrieval/` behind a clear
internal boundary (e.g., `retrieval/orchestration/`).

The evaluation layer consumes retrieval outputs and MLflow runs via stable contracts only.
It MUST NOT be invoked on the hot path of user-facing queries unless explicitly scoped
as an offline or CI benchmark job.

Performance optimizations MUST NOT violate Principles I–V. Caching is allowed only
when cache keys include source version, parser version, and content hashes.

## Development Workflow & Quality Gates

1. **Constitution Check** (in every implementation plan): Explicit pass/fail per
   principle before Phase 0 research and again after Phase 1 design.
2. **Grounding tests**: Golden fixtures from real SEC excerpts; numeric and entity
   assertions compared to known-good parses.
3. **Structure regression tests**: Table and footnote fixtures MUST fail if layout
   metadata is stripped.
4. **Trace contract tests**: Agentic retrieval runs MUST assert required trajectory
   fields and MLflow artifact presence.
5. **Layer contract tests**: Each boundary MUST have contract tests; cross-layer imports
   violating the separation table are build failures.
6. **Evaluation smoke tests**: At least one registered benchmark dataset runs end-to-end
   (accuracy + judge-on-trajectory) in CI or documented offline gate.
7. **Environment gate**: CI MUST use `uv sync --locked` (or equivalent) as the install step.

Complexity that weakens any NON-NEGOTIABLE principle MUST be documented in the plan's
Complexity Tracking table with rejected simpler alternatives.

## Governance

This constitution supersedes ad-hoc conventions, README notes, and inline comments
when they conflict. Amendments require:

1. Documented rationale and semantic-version bump per change magnitude
2. Updates to dependent templates (plan, spec, tasks) and any compliance checklists
3. Migration notes when existing code violates new rules

**Versioning policy** (constitution artifact):

- **MAJOR**: Removal or incompatible redefinition of a principle
- **MINOR**: New principle or materially expanded obligation
- **PATCH**: Clarifications without new obligations

**Compliance review**: Every feature spec, plan, and task list MUST be reviewed against
this document before `/speckit-implement`. `/speckit-analyze` treats constitution
violations as CRITICAL.

Runtime feature guidance lives in feature `plan.md` files and `.cursor/rules/specify-rules.mdc`
(synchronized from the active plan).

**Version**: 1.1.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-05-18
