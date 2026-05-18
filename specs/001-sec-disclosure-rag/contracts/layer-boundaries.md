# Layer Boundary Contracts

Cross-layer communication MUST use these contracts only. Direct imports of internal modules across layers are forbidden (enforced by `import-linter` or contract tests).

## parsing → graph

**Input**: `ParsedDocument` (see [data-model.md](../data-model.md))

**Output**: None (graph layer reads from parsing store path)

**Contract**:
- Parsing exposes `build_parsed_document(filing: FilingRef) -> ParsedDocument`
- Parsing MUST NOT import `graph` or `retrieval`

## graph → retrieval

**Input**: `snapshot_id: str`

**Output**: `GraphSnapshot` via read-only API

**Contract**:
```python
class GraphQueryAPI(Protocol):
    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot: ...
    def get_node(self, snapshot_id: str, node_id: str) -> GraphNode: ...
    def neighbors(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[GraphNode]: ...
    def sections_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]: ...
```

Graph MUST NOT import `retrieval.orchestration` or `evaluation`.

## retrieval → evaluation (public façade)

**Input**: `QueryRequest`

**Output**: `QueryResponse`

**Contract**:
```python
class QueryRequest(BaseModel):
    query: str
    snapshot_id: str
    metadata: dict[str, str] = {}

class QueryResponse(BaseModel):
    answer: AnswerPackage | None
    status: QueryStatus
    mlflow_run_id: str
    trajectory_uri: str  # mlruns:/.../trajectory.json
```

Retrieval MUST NOT import `evaluation`. Evaluation imports only `QueryRequest`/`QueryResponse` types from `src.contracts.query`.

## evaluation → MLflow (read-only)

**Input**: `mlflow_run_id: str`

**Output**: `TrajectoryRecord`

**Contract**:
```python
def load_trajectory(run_id: str) -> TrajectoryRecord: ...
```

Evaluation MUST NOT import `retrieval.orchestration` or LangGraph.

## evaluation → judge (external)

**Input**: `JudgeInput(item, answer, trajectory)`

**Output**: `JudgeVerdict`

Configured via `configs/judges/gemini_2_5_pro.yaml`; uses `GOOGLE_API_KEY` only in evaluation process.
