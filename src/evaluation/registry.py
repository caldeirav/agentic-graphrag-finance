"""Modular benchmark dataset registry."""

from __future__ import annotations

from typing import Protocol

from models.evaluation import BenchmarkItem


class BenchmarkDataset(Protocol):
    name: str

    def load_split(self, split: str) -> list[BenchmarkItem]: ...

    def default_split(self) -> str: ...


class BenchmarkRegistry:
    def __init__(self) -> None:
        self._datasets: dict[str, BenchmarkDataset] = {}

    def register(self, name: str, dataset: BenchmarkDataset) -> None:
        self._datasets[name] = dataset

    def unregister(self, name: str) -> None:
        self._datasets.pop(name, None)

    def get(self, name: str) -> BenchmarkDataset:
        if name not in self._datasets:
            raise KeyError(f"dataset not registered: {name}")
        return self._datasets[name]

    def list_datasets(self) -> list[str]:
        return sorted(self._datasets.keys())


def default_registry() -> BenchmarkRegistry:
    import os

    from evaluation.datasets.custom_judge import CustomJudgeDataset
    from evaluation.datasets.finagentbench import FinAgentBenchDataset
    from evaluation.datasets.financebench import FinanceBenchDataset
    from evaluation.datasets.finder import FinDERDataset

    reg = BenchmarkRegistry()
    reg.register("finder", FinDERDataset())
    reg.register("finagentbench", FinAgentBenchDataset())
    reg.register("financebench", FinanceBenchDataset())
    reg.register(
        "custom-judge",
        CustomJudgeDataset(version=os.getenv("CUSTOM_JUDGE_VERSION", "0.0.0-draft")),
    )
    return reg
