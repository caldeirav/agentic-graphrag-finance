# Benchmark Registry Contract

**Package**: `src/evaluation/registry.py`

## Plugin interface

```python
class BenchmarkDataset(Protocol):
    name: str  # "finder" | "finagentbench" | "financebench"

    def load_split(self, split: str) -> list[BenchmarkItem]: ...

    def default_split(self) -> str: ...
```

## Registration

```python
registry.register("finder", FinDERDataset(data_dir=Path("data/benchmarks/finder")))
registry.register("finagentbench", FinAgentBenchDataset(...))
registry.register("financebench", FinanceBenchDataset(...))
```

Adding a dataset: implement `BenchmarkDataset`, register in `evaluation/datasets/__init__.py` — **no changes** to `retrieval/`.

## Runner contract

```python
class EvaluationRunner:
    def run_suite(
        self,
        suite: BenchmarkSuite,
        snapshot_id: str,
        query_service: QueryService,
    ) -> EvaluationRun: ...
```

`BenchmarkSuite` lists `(dataset_name, split, max_items?)` tuples.

## Report outputs

| Artifact | Contents |
|----------|----------|
| `summary.json` | Aggregate accuracy, alignment, trajectory fidelity |
| `by_dataset.json` | Per-dataset breakdown |
| `by_operation_class.json` | QUALITATIVE, ADD, SUB, MUL, DIV, COMPOSITIONAL |
| `ranking.json` | MRR, MAP, nDCG@10 means |
| `items.parquet` | Per-item scores + mlflow_run_id |

All logged under MLflow parent run `benchmark-{suite}-{timestamp}`.

## Judge rubric (Gemini 2.5 Pro)

Prompt templates in `configs/judges/gemini_2_5_pro.yaml`:

1. **value_alignment**: Exact match of numeric claims to ground truth (tolerance rules per dataset)
2. **claim_presence**: Required factual claims appear in answer
3. **trajectory_fidelity**: MLflow trajectory sections/nodes align with expected path rubric

Judge MUST receive: question, answer text, citations, trajectory JSON, ground truth (if any).
