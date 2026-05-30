# Custom Judge Dataset Adapter Contract (011)

**Package**: `src/evaluation/datasets/custom_judge.py`  
**Registry name**: `custom-judge`

## Plugin interface

Implements existing `BenchmarkDataset` protocol ([001 benchmark-registry](../../001-sec-disclosure-rag/contracts/benchmark-registry.md)).

```python
class CustomJudgeDataset:
    name: str = "custom-judge"

    def __init__(self, version: str = "1.0.0", bundle_root: Path | None = None): ...

    def load_split(self, split: str) -> list[BenchmarkItem]: ...

    def default_split(self) -> str: ...  # "dev"

    def manifest(self) -> DatasetManifest: ...

    def corpus_bundle(self) -> CorpusBundle: ...
```

## Registration

```python
# evaluation/registry.py default_registry()
reg.register("custom-judge", CustomJudgeDataset(version=os.getenv("CUSTOM_JUDGE_VERSION", "1.0.0")))
```

Unregister: `registry.unregister("custom-judge")` — no retrieval code changes.

## JSONL row → BenchmarkItem mapping

| JSONL field | BenchmarkItem field |
|-------------|---------------------|
| `item_id` | `item_id` |
| `question` | `question` |
| `ground_truth` | `ground_truth` |
| `relevant_chunk_ids` | `relevant_chunk_ids` |
| `expected_bindings` | `expected_bindings` |
| `multi_filing_required` | `multi_filing_required` |
| `operation_class` | `operation_class` |
| `expected_section_paths` | `expected_section_paths` (new model field) |

## Offline evaluation

When loading items, adapter exposes:

- `bundle_root / corpus_bundle.corpus_root` as graph store override
- `snapshot_id` from manifest (composite or per-item issuer snapshot resolution)

Runner MUST set `OFFLINE_BENCHMARK=1` and refuse EDGAR fetch if bundle paths missing.

## Splits

| Split | File | v1 |
|-------|------|-----|
| `dev` | `items/dev.jsonl` | Primary (≥200 items) |
| `test` | `items/test.jsonl` | Optional future holdout |

## Synthetic fallback

**Disabled** for `custom-judge` — missing bundle or JSONL raises `FileNotFoundError` with LFS pull instructions (no `_synthetic_items`).
