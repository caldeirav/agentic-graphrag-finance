# Research: Agentic SEC Disclosure Reasoning & Benchmarking

**Date**: 2026-05-18 | **Plan**: [plan.md](./plan.md)

## R1: Workspace & Dependency Management

**Decision**: Use `uv` exclusively with `pyproject.toml` + committed `uv.lock`; Python 3.12+.

**Rationale**: Constitution Principle V mandates deterministic, locked builds. `uv` provides fast sync and matches project governance.

**Alternatives considered**:
- Poetry/pip — rejected (constitution violation)
- Docker-only env — deferred as optional CI image; not primary dev path

## R2: SEC Parsing with Docling XBRL

**Decision**: Docling pipeline with custom YAML referencing `xbrl_conversion` layout paradigms for 10-K/10-Q HTML and inline XBRL exhibits.

**Rationale**: User mandate; Docling preserves tables/footnotes better than naive HTML stripping; aligns with Principle II.

**Alternatives considered**:
- Raw BeautifulSoup + custom table parser — rejected (high maintenance, layout loss risk)
- Commercial OCR — rejected for digital-native EDGAR HTML

**Open implementation notes**:
- Map Docling `DoclingDocument` export to internal `ParsedDocument` without flattening tables to plain text
- Flag `parse_confidence` on merged-cell and non-standard XBRL blocks

## R3: Knowledge Graph via docling-graph

**Decision**: Use docling-graph to emit hierarchical ER schema, then normalize into internal `GraphDocument` (NetworkX) with typed node/edge enums.

**Rationale**: Native bridge from Docling output; supports document → section → chunk hierarchy and reference edges.

**Alternatives considered**:
- Neo4j immediately — deferred (operational overhead for v1); GraphML + manifest sufficient for local dev/benchmarks
- Manual NetworkX-only construction — rejected (duplicates docling-graph value)

**Edge mapping**:
| Internal edge type | Source |
|--------------------|--------|
| `CONTAINS` | Document→section→chunk hierarchy |
| `NEXT` | Sequential sections/chunks |
| `FOOTNOTE_OF` | Footnote linker |
| `REFERENCES` | Cross-ref / exhibit |
| `TEMPORAL_TRANSITION` | Same issuer, period t → t+1 filings |

## R4: Local LLM via LM Studio (Qwen)

**Decision**: `langchain_openai.ChatOpenAI` pointed at LM Studio OpenAI-compatible base URL; model id `qwen/qwen3.6-35b-a3b`.

**Rationale**: User mandate for local primary intelligence; OpenAI-compatible API minimizes custom client code.

**Alternatives considered**:
- Ollama direct — rejected (user specified LM Studio)
- Cloud Qwen API — rejected for retrieval path (local-first); acceptable only for judge if needed (judge uses Gemini per spec)

**Configuration**:
```yaml
# configs/lm_studio.yaml
base_url: "${LM_STUDIO_BASE_URL:-http://localhost:1234/v1}"
model: "qwen/qwen3.6-35b-a3b"
temperature: 0.1
max_tokens: 4096
```

## R5: LangGraph Three-Stage Router

**Decision**: Single `StateGraph` with nodes `macro_router` → `meso_router` → `micro_extractor` → `synthesize`; conditional edge from `synthesize` to END or `InsufficientEvidence` terminal.

**Rationale**: Matches spec FR-007–FR-010; keeps orchestration inside `retrieval/orchestration/` per constitution.

**Alternatives considered**:
- Separate top-level `agent/` package — rejected (constitution)
- Single-shot ReAct without staged routing — rejected (fails meso/micro precision goals)

**State persistence**: In-memory per query; MLflow captures transitions (Segment 3).

## R6: MLflow + LangGraph Tracing

**Decision**: Enable MLflow LangChain/LangGraph autolog; supplement with explicit `TrajectoryRecord` JSON artifact per query run.

**Rationale**: Constitution Principle III; evaluation layer reads MLflow without importing LangGraph.

**Alternatives considered**:
- LangSmith only — rejected (user mandated MLflow)
- Custom JSON logs — retained as artifact backup inside MLflow run

**Implementation pattern**:
```python
mlflow.langchain.autolog()
mlflow.set_experiment("sec-disclosure-rag")
with mlflow.start_run(run_name=query_id):
    result = compiled_graph.invoke(initial_state)
    mlflow.log_dict(trajectory.model_dump(), "trajectory.json")
```

## R7: External Judge (Gemini 2.5 Pro)

**Decision**: `langchain_google_genai.ChatGoogleGenerativeAI` with model `gemini-2.5-pro` (or current stable id from Google docs) in `evaluation/judges/` only.

**Rationale**: Constitution requires external judge separate from retrieval LLM; user mandate.

**Alternatives considered**:
- Same Qwen for judging — rejected (insufficient independence)
- Human-only eval — rejected for scale; human audit spot-checks optional later

**Rubric dimensions** (per benchmark item):
1. Exact numeric/value alignment
2. Target claim presence / factual alignment
3. Trajectory fidelity vs expected evidence path
4. Operation class tag: qualitative | add | sub | mul | div | compositional

## R8: Benchmark Datasets (Modular Registry)

**Decision**: Plugin registry pattern (`evaluation/registry.py`) with one module per dataset; loaders normalize to `BenchmarkItem`.

**Rationale**: FR-013/FR-014; SC-007 modularity.

| Dataset | Loader responsibility |
|---------|----------------------|
| FinDER | Load public JSON/Parquet; map to issuer + question + relevance labels |
| FinAgentBench | Agent-task format → `BenchmarkItem` + optional trajectory rubric |
| FinanceBench | QA pairs + ground truth answers |

**Pilot scope**: Minimum 100 items each or full dev split if smaller (per spec SC-004).

## R9: Ranking & Trajectory Metrics

**Decision**:
- **MRR, MAP, nDCG@k**: `evaluation/metrics/ranking.py` using meso/micro retrieved chunk IDs vs labeled relevant chunk sets
- **Trajectory fidelity**: Judge score 0–1 + structural overlap (visited section path vs gold path)

**Rationale**: Spec FR-018/FR-019; user request for MRR, MAP, nDCG, trajectory fidelity.

## R10: Graph Persistence Format

**Decision**: NetworkX → GraphML on disk + JSON `manifest.json` (snapshot metadata, parser/graph builder versions, SHA-256 of source filings).

**Rationale**: Human-inspectable, queryable via `networkx.read_graphml`, no DB ops for v1.

**Alternatives considered**:
- SQLite adjacency — viable Phase 2 if graph size requires
- In-memory only — rejected (benchmark reproducibility needs snapshots)

## Resolved Clarifications

All technical-context items resolved; no blocking NEEDS CLARIFICATION remains for Phase 1 design.
