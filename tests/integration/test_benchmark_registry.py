from evaluation.datasets.financebench import FinanceBenchDataset
from evaluation.registry import BenchmarkRegistry


class _StubDataset:
    name = "stub"

    def default_split(self) -> str:
        return "dev"

    def load_split(self, split: str):
        from models.evaluation import BenchmarkItem

        return [BenchmarkItem(item_id="stub-1", dataset="stub", question="q?")]


def test_registry_plugin_swap():
    reg = BenchmarkRegistry()
    reg.register("stub", _StubDataset())
    assert reg.get("stub").name == "stub"
    reg.unregister("stub")
    assert "stub" not in reg.list_datasets()
    assert FinanceBenchDataset().load_split("dev")
