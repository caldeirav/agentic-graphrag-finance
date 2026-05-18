from pathlib import Path

from evaluation.datasets._base import load_jsonl_dataset
from models.evaluation import BenchmarkItem


class FinDERDataset:
    name = "finder"

    def __init__(self, data_dir: Path | None = None) -> None:
        self._dir = data_dir or Path("data/benchmarks/finder")

    def default_split(self) -> str:
        return "dev"

    def load_split(self, split: str) -> list[BenchmarkItem]:
        return load_jsonl_dataset(self.name, self._dir / f"{split}.jsonl")
