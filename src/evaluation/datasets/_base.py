"""Shared dataset loader utilities."""

from __future__ import annotations

import json
from pathlib import Path

from models.enums import OperationClass
from models.evaluation import BenchmarkItem, GroundTruth


def load_jsonl_dataset(
    name: str,
    path: Path,
    *,
    split: str = "dev",
    max_items: int | None = None,
) -> list[BenchmarkItem]:
    if not path.exists():
        return _synthetic_items(name, count=max_items or 3)

    items: list[BenchmarkItem] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        items.append(
            BenchmarkItem(
                item_id=str(row.get("id", len(items))),
                dataset=name,
                question=row.get("question", row.get("query", "")),
                ground_truth=GroundTruth(
                    answer=row.get("answer"),
                    relevant_chunk_ids=row.get("relevant_chunk_ids", []),
                    rubric=row.get("rubric"),
                ),
                relevant_chunk_ids=row.get("relevant_chunk_ids", []),
                operation_class=OperationClass(row.get("operation_class", "QUALITATIVE")),
            )
        )
        if max_items and len(items) >= max_items:
            break
    return items


def _synthetic_items(name: str, *, count: int = 3) -> list[BenchmarkItem]:
    return [
        BenchmarkItem(
            item_id=f"{name}-synthetic-{i}",
            dataset=name,
            question=f"What is the total assets figure in the latest 10-K? (synthetic {i})",
            ground_truth=GroundTruth(answer="N/A", relevant_chunk_ids=[]),
            operation_class=OperationClass.QUALITATIVE,
        )
        for i in range(count)
    ]
