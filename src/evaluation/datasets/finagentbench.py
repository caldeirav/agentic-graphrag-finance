import json
from pathlib import Path

from evaluation.datasets._base import load_jsonl_dataset
from models.corpus import CorpusTemporalScope
from models.enums import OperationClass
from models.evaluation import BenchmarkItem, ExpectedBindings, GroundTruth


def _parse_operation_class(raw: object) -> OperationClass:
    key = str(raw or "qualitative").lower()
    if key in ("numeric", "add"):
        return OperationClass.ADD
    return OperationClass.QUALITATIVE


class FinAgentBenchDataset:
    name = "finagentbench"

    def __init__(self, data_dir: Path | None = None) -> None:
        self._dir = data_dir or Path("data/benchmarks/finagentbench")

    def default_split(self) -> str:
        return "dev"

    def load_split(self, split: str) -> list[BenchmarkItem]:
        return load_jsonl_dataset(self.name, self._dir / f"{split}.jsonl")

    def _macro_binding_path(self) -> Path | None:
        candidates = [
            self._dir / "macro_binding.jsonl",
            Path("tests/fixtures/finagentbench/macro_binding.jsonl"),
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def load_macro_binding_slice(self) -> list[BenchmarkItem]:
        path = self._macro_binding_path()
        if path is None:
            return []
        items: list[BenchmarkItem] = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            ts = row.get("temporal_scope") or {}
            items.append(
                BenchmarkItem(
                    item_id=str(row["item_id"]),
                    dataset=row.get("dataset", self.name),
                    question=row["question"],
                    operation_class=_parse_operation_class(row.get("operation_class")),
                    temporal_scope=CorpusTemporalScope(
                        anchor=ts.get("anchor"),
                        periods=list(ts.get("periods") or []),
                        compare_periods=list(ts.get("compare_periods") or []),
                        accessions=list(ts.get("accessions") or []),
                    ),
                    expected_bindings=ExpectedBindings.model_validate(
                        row["expected_bindings"]
                    ),
                    multi_filing_required=bool(row.get("multi_filing_required", False)),
                    expect_binding_failure=bool(row.get("expect_binding_failure", False)),
                    ground_truth=GroundTruth(answer=row.get("answer")),
                )
            )
        return items

    def load_gold_path_slice(self, fixtures_dir: Path | None = None) -> list[dict]:
        base = fixtures_dir or Path("tests/fixtures/gold_path")
        path = base / "gold_path.jsonl"
        if not path.exists():
            path = self._dir / "gold_path.jsonl"
        if not path.exists():
            return []
        rows: list[dict] = []
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
