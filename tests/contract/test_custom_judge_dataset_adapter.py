"""Contract tests for custom-judge dataset adapter (012)."""

from pathlib import Path

import pytest

from evaluation.datasets.custom_judge import CustomJudgeDataset
from evaluation.registry import default_registry

FIXTURE = Path("tests/fixtures/custom_judge")


def test_registry_includes_custom_judge():
    reg = default_registry()
    assert "custom-judge" in reg.list_datasets()


def test_adapter_maps_jsonl_to_benchmark_item():
    ds = CustomJudgeDataset(bundle_root=FIXTURE)
    items = ds.load_split("dev")
    assert len(items) == 3
    assert items[0].expected_section_paths


def test_adapter_no_synthetic_fallback(tmp_path: Path):
    ds = CustomJudgeDataset(bundle_root=tmp_path)
    with pytest.raises(FileNotFoundError, match="Synthetic fallback disabled"):
        ds.load_split("dev")
