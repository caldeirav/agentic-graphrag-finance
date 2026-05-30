"""Near-duplicate question deduplication for generated items (012)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from models.benchmark_generation import GeneratedBenchmarkItem


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def is_duplicate(
    candidate: GeneratedBenchmarkItem,
    accepted: list[GeneratedBenchmarkItem],
    *,
    threshold: float,
) -> bool:
    for prior in accepted:
        if similarity(candidate.question, prior.question) >= threshold:
            return True
    return False


def deduplicate_items(
    items: list[GeneratedBenchmarkItem],
    *,
    threshold: float,
) -> tuple[list[GeneratedBenchmarkItem], list[GeneratedBenchmarkItem]]:
    accepted: list[GeneratedBenchmarkItem] = []
    rejected: list[GeneratedBenchmarkItem] = []
    for item in items:
        if item.validation_status != "accepted":
            rejected.append(item)
            continue
        if is_duplicate(item, accepted, threshold=threshold):
            rejected.append(
                item.model_copy(
                    update={
                        "validation_status": "rejected",
                        "validation_errors": [*item.validation_errors, "duplicate_question"],
                    }
                )
            )
        else:
            accepted.append(item)
    return accepted, rejected
