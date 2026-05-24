# Feature Specification: Auditable MLflow Trajectories & LLM-as-Judge Evaluation

**Feature Branch**: `010-mlflow-trajectory-judge-eval`

**Created**: 2026-05-24

**Status**: Draft

**Input**: User description: "Implement complete, auditable MLflow trajectories for every production and benchmark query: structured plan (intent, steps considered, chosen path rationale), document route (filing ids, form types, period-ends), graph traversal (node id, node type, edge id, edge type per hop), and evidence (stable content hash and citation label per chunk). Provide a validator that marks trajectories incomplete or non-reproducible when mandatory fields are missing. Build an evaluation on the agentic trace based on llm-as-judge which must consume trajectories without importing retrieval internals. Define and implement key evaluation criteria that are relevant to understand the approach of the agent (quality of trajectory, llm decisions, data retrieval and synthesis). Integrate the evaluation scores / assessments into the console output as well. Success: at least 90% of benchmark runs produce trajectories passing validation; incomplete runs are flagged and excluded from fidelity aggregates; mlflow interface shows evaluation criteria and score with ability to drill down into the data and reason, and scores allow to identify the part of the processing workflow that is not performing."

## Clarifications

### Session 2026-05-24

- Q: What is the authoritative observability sink for trajectories and judge scores? → A: **MLflow** — each ask/benchmark run is an MLflow run with structured trajectory artifacts and separate judge-result artifacts; operators may use the MLflow UI or console summaries, but persistence and drill-down are MLflow-first (aligned with [agent tracing](https://mlflow.org/llm-tracing/#agent-tracing) and [LLM-as-a-judge](https://mlflow.org/llm-as-a-judge) capabilities).
- Q: May the evaluation layer call back into retrieval code to score a run? → A: **No** — judges and fidelity aggregators consume only serialized trajectory payloads (and optionally the final answer text); they MUST NOT import retrieval orchestration, graph stores, or ingestion modules.
- Q: Which runs require a full trajectory? → A: **Every production `ask` and every benchmark item** that executes the agent graph, including runs that end in scope errors or insufficient evidence; failed macro binding still produces a trajectory with explicit failure status and empty downstream sections where applicable.
- Q: When should LLM-as-judge evaluation run? → A: **Every production `ask` and every benchmark item** — judge runs automatically and **blocks** completion until scores and justifications are persisted (answer and console summary follow validation + judge).
- Q: How should the canonical trajectory be stored in MLflow? → A: **MLflow Trace spans primary** — native LangGraph/MLflow [agent tracing](https://mlflow.org/llm-tracing/#agent-tracing) is the authoritative drill-down surface; explicit JSON trajectory export is **secondary** (derived snapshot for validator, judge, and offline benchmarks).
- Q: What should happen when blocking judge evaluation fails? → A: **Retry then degrade** — up to **3** automatic retries with backoff; if all fail, still emit answer + trajectory, mark judge `failed`/`skipped`, exclude from judge aggregates, and surface a console warning (non-fatal).
- Q: What scoring scale should judges use per criterion? → A: **0.0–1.0** continuous per criterion with written justification; console highlights weakest stage when any criterion is below **0.6** (configurable threshold).
- Q: Which benchmark suite defines the 90% trajectory-validation pass gate? → A: **Combined in-repo slice** — gold-path + macro-binding + new trajectory-validation fixtures (minimum **50** items) on a fixed issuer corpus (e.g. AAPL materialized snapshot).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Trajectory on Every Query (Priority: P1)

An engineer or analyst runs a production question or a benchmark item and receives a single, machine-readable **agent trajectory** that fully explains what the system decided and why: planning intent, filings considered, graph hops taken, and evidence selected—with enough detail to reproduce the audit chain without re-running retrieval code.

**Why this priority**: Constitution principle III (Traceability) and all downstream evaluation depend on a complete, stable trajectory schema.

**Independent Test**: Run ten diverse `ask` queries (numeric, qualitative, multi-filing YoY); verify each MLflow run contains a validated trajectory artifact with all mandatory sections populated or explicitly marked not applicable with reason codes.

**Acceptance Scenarios**:

1. **Given** a successful ask against a materialized issuer snapshot, **When** the run completes, **Then** the trajectory includes plan (intent summary, steps considered, chosen path rationale), document route (each bound filing’s identifier, form type, period-of-report end), graph traversal (every recorded hop with node id, node type, edge id when present, edge type), and evidence (each cited chunk with stable content hash and citation label).
2. **Given** a benchmark batch over a fixed item set, **When** each item finishes, **Then** every item’s MLflow run references the same trajectory schema version and correlates to query id, snapshot version, and issuer identity.
3. **Given** macro binding fails before meso navigation, **When** the run ends, **Then** the trajectory still records plan attempt, failure rationale, document route context available, and marks graph traversal and evidence as absent with standardized reason codes—not silent omission.

---

### User Story 2 - Trajectory Validator & Reproducibility Gate (Priority: P1)

A release engineer runs benchmarks and needs automated assurance that trajectories are **complete** and **reproducible** (stable identifiers and hashes, no orphan hops, filing route consistent with evidence accession prefixes) before fidelity or judge scores are aggregated.

**Why this priority**: The 90% pass-rate success metric is meaningless without a deterministic validator; incomplete runs must be excluded from aggregates.

**Independent Test**: Feed valid and intentionally broken trajectory fixtures to the validator; verify pass/fail, reason codes, and exclusion from aggregate metrics.

**Acceptance Scenarios**:

1. **Given** a trajectory missing evidence content hashes, **When** validation runs, **Then** status is `incomplete` with field-level reason codes and the run is flagged for exclusion from fidelity aggregates.
2. **Given** a trajectory where graph hops reference node ids not prefixed by any document route accession, **When** validation runs, **Then** status is `non_reproducible` with hop-level diagnostics.
3. **Given** a trajectory passing all mandatory field checks, **When** validation runs, **Then** status is `complete` and the run is eligible for judge evaluation and fidelity aggregation.

---

### User Story 3 - LLM-as-Judge on Trajectories (Priority: P2)

A researcher evaluates agent quality by having an external judge model score each run’s trajectory and answer along dimensions that reflect **how** the agent worked—not only whether the final text looks plausible.

**Why this priority**: Grounded financial Q&A requires judging retrieval faithfulness and decision quality, not surface fluency alone.

**Independent Test**: Run judge evaluation on a frozen set of trajectory JSON artifacts with no retrieval code on the classpath for the eval module; verify scores, per-criterion justifications, and MLflow logging.

**Acceptance Scenarios**:

1. **Given** a benchmark item with a complete trajectory, **When** judge evaluation runs, **Then** the system produces scores and written justifications for each defined criterion (see FR-012) without importing retrieval internals.
2. **Given** a trajectory marked `incomplete`, **When** judge evaluation is invoked, **Then** judges are skipped or produce a standardized “not evaluable” outcome and the run remains excluded from headline fidelity aggregates.
3. **Given** judge results for a batch, **When** an operator opens the MLflow run, **Then** they can use the **Trace** UI and judge artifacts to see per-criterion scores, overall assessment, and which workflow stage underperformed (macro, intent, meso, micro, synthesis).

---

### User Story 4 - Console & MLflow Operator Visibility (Priority: P2)

An operator debugging a live ask wants evaluation outcomes visible in the **terminal trace** (alongside existing stage panels) and in **MLflow** without writing custom scripts.

**Why this priority**: Closes the loop between benchmark gates and day-to-day debugging; satisfies “identify which part of the workflow is not performing.”

**Independent Test**: Run live `ask` with `--trace normal`; verify stderr shows validation status and criterion scores summary before the answer footer; verify MLflow artifacts match.

**Acceptance Scenarios**:

1. **Given** `--trace normal` and a completed ask with judge evaluation, **When** the run finishes, **Then** stderr includes trajectory validation status and a compact per-criterion score summary with the lowest-scoring stage called out.
2. **Given** a benchmark report, **When** the operator reviews aggregate metrics, **Then** only runs with `complete` trajectories contribute to fidelity and judge headline scores; incomplete counts are reported separately.
3. **Given** an MLflow run with judge artifacts, **When** the operator inspects the run, **Then** they can open trajectory, validation report, and per-criterion judge justifications in one place.

---

### Edge Cases

- What happens when the local LLM returns empty synthesis text but deterministic fallback produces an answer? Trajectory MUST record synthesis path (live vs fallback) and evidence actually sent to the model.
- What happens when mock modes (`USE_MOCK_LLM`) skip live LLM calls? Trajectory MUST label proposal sources and judge evaluation MAY use a reduced criterion set documented for mock runs, but validation rules still apply to structural fields.
- What happens when a hop uses only edge type without edge id (structural containment)? Validator MUST accept catalog-allowed patterns and reject hops with neither edge id nor edge type.
- What happens when evidence count exceeds prompt budget? Trajectory MUST list all evidence chunks selected for synthesis ranking, not only the subset placed in the prompt.
- What happens when two benchmark workers write concurrently? Each run MUST have a unique MLflow run id; trajectory artifacts MUST NOT be merged across items.
- What happens when the judge API fails after retries? The ask completes with `judge_status=degraded`; answer and trajectory remain available; judge headline metrics exclude that run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST record one **agent trajectory** per production `ask` and per benchmark execution as an **MLflow Trace** (LangGraph/LangChain autolog spans) linked to the run; operators drill down via the MLflow Trace UI as the primary interface.
- **FR-001a**: System MUST also emit a **derived JSON trajectory snapshot** (versioned) exported from trace + structured agent state for validator, judge, and CI; the JSON is secondary to the trace for human exploration but primary for deterministic evaluation pipelines.
- **FR-002**: Trajectory MUST include a **plan** section: query intent summary, enumerated steps or stages considered, and rationale for the chosen path (including rejected alternatives when recorded by the agent).
- **FR-003**: Trajectory MUST include a **document route** section listing every bound filing with accession identifier, form type, and period-of-report end date (and fiscal period label when available).
- **FR-004**: Trajectory MUST include **graph traversal** as an ordered list of hops; each hop MUST record node id, node type, edge type, and edge id when the graph edge exists; hops MUST be attributable to a stage (macro, meso, micro, or audit).
- **FR-005**: Trajectory MUST include **evidence** as a list of chunks used or shortlisted for synthesis; each entry MUST include stable content hash, citation label, source type (numeric taxonomy vs narrative), accession, and section or chunk node id.
- **FR-006**: System MUST provide a **trajectory validator** that assigns one of: `complete`, `incomplete`, or `non_reproducible`, with machine-readable reason codes per failed rule.
- **FR-007**: Validator MUST treat missing mandatory fields, empty document route on successful numeric/qualitative asks, hops without node type, evidence without content hash, and accession mismatches between route and evidence as failures.
- **FR-008**: Benchmark and fidelity aggregations MUST **exclude** runs not marked `complete` and MUST report counts of excluded runs separately from headline metrics.
- **FR-009**: System MUST provide an **evaluation module** that runs **LLM-as-judge** assessment on serialized trajectories (and final answer text) without importing retrieval, ingestion, or graph builder modules.
- **FR-009a**: LLM-as-judge MUST run on **every** production `ask` and **every** benchmark item after trajectory validation and **before** the run is considered complete (blocking); mock-judge bypass (`USE_MOCK_JUDGE`) is permitted only in CI with documented reduced criteria.
- **FR-009b**: On judge failure after **up to 3** retries, the system MUST **degrade gracefully**: persist answer and trajectory, set judge status to `failed` or `skipped`, log the error on the MLflow run, exclude the run from judge aggregates, and print a console warning—without changing `QueryStatus` from a successful retrieval outcome.
- **FR-010**: Judge evaluation MUST produce per-criterion scores on a **0.0–1.0** scale and natural-language justifications suitable for human audit (aligned with MLflow [LLM-as-a-judge](https://mlflow.org/llm-as-a-judge) patterns).
- **FR-011**: Judge evaluation MUST log results to the same observability run as the trajectory (separate artifact(s), linked by run id).
- **FR-012**: System MUST define and apply at minimum these judge criteria, each scored and justified independently:
  - **Trajectory completeness & coherence** — Does the recorded plan, route, hops, and evidence tell a consistent story?
  - **Routing & LLM decision quality** — Were filing bindings, intent classification, and section choices reasonable for the question?
  - **Retrieval fidelity** — Does evidence support the question; are periods and form types aligned to the route?
  - **Synthesis grounding** — Does the final answer stay within cited evidence without unsupported claims?
- **FR-013**: Console trace (`--trace normal` or `verbose`) MUST surface trajectory validation status and a summary of judge scores (0.0–1.0 per criterion), highlighting the weakest criterion and associated workflow stage when any score is below **0.6** (configurable via `configs/trajectory_judge.yaml` or equivalent).
- **FR-014**: System MUST support benchmark batches where **at least 90%** of items in the **reference suite** (gold-path + macro-binding + trajectory-validation fixtures, ≥50 items, fixed issuer corpus) produce trajectories passing validation (`complete`); releases MUST fail a benchmark gate when pass rate falls below this threshold.
- **FR-015**: MLflow presentation MUST allow operators to inspect the **Trace** view (spans per stage, LLM I/O), derived JSON snapshot, validation report, and judge per-criterion results for a run without custom tooling.
- **FR-016**: Trajectory schema version MUST be recorded in each artifact; breaking changes require a version bump and migration note in benchmark contracts.

### Key Entities

- **Agent trajectory**: Canonical audit record for one query execution; subsumes plan, document route, traversal, evidence, stage timings, and status.
- **Trajectory validation result**: Outcome (`complete` | `incomplete` | `non_reproducible`), rule-level findings, schema version, timestamp.
- **Judge criterion result**: Criterion id, score (**0.0–1.0**), justification text, optional stage attribution (macro | intent | meso | micro | synthesis).
- **Benchmark fidelity aggregate**: Headline metrics computed only over `complete` trajectories; includes exclusion counts and per-criterion judge means.
- **Run correlation bundle**: Query text, issuer, snapshot id, MLflow run id, trajectory artifact uri, validation status, judge summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least **90%** of items in the **combined reference suite** (gold-path + macro-binding + trajectory-validation fixtures, ≥50 items) produce trajectories validated as `complete` on a fixed issuer corpus (e.g. AAPL materialized snapshot) in CI or release gate.
- **SC-002**: **100%** of runs excluded for incomplete or non-reproducible trajectories are omitted from fidelity and judge headline aggregates, with exclusion counts visible in benchmark summary output.
- **SC-003**: Operators can identify the **underperforming workflow stage** (macro, intent, meso, micro, or synthesis) for any judged run in under **2 minutes** using the MLflow **Trace** UI, judge artifacts, or console trace summary without re-running the query.
- **SC-004**: Judge evaluation module passes an import-boundary check: **zero** imports from retrieval orchestration, graph execution, or ingestion packages.
- **SC-005**: For a pilot set of **20** diverse queries, at least **80%** of judge “synthesis grounding” scores agree with human reviewer pass/fail when compared in a blind review sample.
- **SC-006**: Console trace at `normal` depth adds validation + judge summary in **under 15 lines** so operators are not overwhelmed while meeting FR-013.
- **SC-007**: **100%** of production `ask` runs that reach synthesis produce judge artifacts on the same MLflow run before the CLI prints final status (excluding runs aborted before trajectory assembly).

## Assumptions

- **MLflow Traces** (via `mlflow.langchain.autolog()` / LangGraph integration) are the **authoritative** operator-facing trajectory; per-stage JSON files (`trajectory.json`, `macro_binding.json`, etc.) are either folded into trace span attributes or mirrored into the derived snapshot export.
- MLflow 3.x supports agent tracing and [LLM-as-a-judge](https://mlflow.org/llm-as-a-judge) evaluation logging; the derived JSON snapshot remains required for import-boundary-safe eval modules.
- External judge uses the project’s established judge provider (e.g. Gemini) with mock bypass for CI; criterion prompts are English and tailored to SEC disclosure Q&A.
- Production `ask` latency includes blocking judge time; operators accept additional wait for auditability in v1.
- Reference benchmark suite for the 90% gate is the **combined in-repo slice**: existing gold-path and macro-binding items plus new trajectory-validation fixtures, **minimum 50 items** total on a fixed issuer corpus (e.g. AAPL).
- Console trace registry (007) is extended, not duplicated—validation and judge summaries are new stage or footer payloads derived from the same structured fields logged to MLflow.
- “Steps considered” may be represented as stage-level decision enumerations (e.g. candidate sections ranked, rejected hops) when a single monolithic plan object is not produced by the graph.

## Dependencies

- **007** ask console trace — display layer for validation and judge summaries.
- **008** autonomous macro routing — macro section of plan and document route.
- **009** graph-native meso/micro — navigation trace and hop-level traversal detail.
- **001** evaluation layer boundaries — judges remain independent of retrieval internals.
