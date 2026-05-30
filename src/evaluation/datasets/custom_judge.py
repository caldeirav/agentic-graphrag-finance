"""Custom-judge published dataset adapter (012)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from models.benchmark_generation import CorpusBundle, DatasetManifest
from models.enums import OperationClass
from models.evaluation import BenchmarkItem, ExpectedBindings, GroundTruth


class CustomJudgeDataset:
    name = "custom-judge"

    def __init__(self, version: str | None = None, bundle_root: Path | None = None) -> None:
        self._version = version or os.getenv("CUSTOM_JUDGE_VERSION", "0.0.0-draft")
        if bundle_root is not None:
            self._root = bundle_root
        else:
            env_root = os.getenv("CUSTOM_JUDGE_BUNDLE_ROOT")
            if env_root:
                self._root = Path(env_root)
            else:
                published = Path(f"data/benchmarks/custom-judge/v{self._version}")
                fixture = Path("tests/fixtures/custom_judge")
                self._root = published if published.is_dir() else fixture

    def default_split(self) -> str:
        return "dev"

    def _items_path(self, split: str) -> Path:
        return self._root / "items" / f"{split}.jsonl"

    def manifest(self) -> DatasetManifest:
        manifest_path = self._root / "manifest.json"
        if not manifest_path.is_file():
            msg = (
                f"Custom-judge bundle missing at {manifest_path}. "
                "Run `git lfs pull` for data/benchmarks/custom-judge/**/corpus/**"
            )
            raise FileNotFoundError(msg)
        return DatasetManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))

    def corpus_bundle(self) -> CorpusBundle:
        return self.manifest().corpus_bundle

    def load_split(self, split: str) -> list[BenchmarkItem]:
        path = self._items_path(split)
        if not path.is_file():
            msg = (
                f"Custom-judge split missing: {path}. "
                "Synthetic fallback disabled for custom-judge (FR-010)."
            )
            raise FileNotFoundError(msg)
        items: list[BenchmarkItem] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            gt = row.get("ground_truth") or {}
            items.append(
                BenchmarkItem(
                    item_id=row["item_id"],
                    dataset=self.name,
                    question=row["question"],
                    ground_truth=GroundTruth(
                        answer=gt.get("answer"),
                        rubric=gt.get("rubric"),
                        relevant_chunk_ids=gt.get("relevant_chunk_ids", []),
                    ),
                    relevant_chunk_ids=row.get("relevant_chunk_ids", []),
                    expected_bindings=ExpectedBindings.model_validate(
                        row.get("expected_bindings", {})
                    ),
                    expected_section_paths=row.get("expected_section_paths", []),
                    multi_filing_required=row.get("multi_filing_required", False),
                    operation_class=OperationClass(
                        str(row.get("operation_class", OperationClass.QUALITATIVE.value)).upper()
                    ),
                )
            )
        return items
