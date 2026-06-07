"""Pre-write normalization for reproduction benchmark results (015)."""

from __future__ import annotations

import re

from models.evaluation import BenchmarkResult
from tracing.trajectory_export import normalize_trajectory_state

_NUMERIC_TOKEN = re.compile(r"\b\d[\d,]*\.?\d*\b")


def ensure_trajectory_citation_consistency(result: BenchmarkResult) -> BenchmarkResult:
    """Hydrate trajectory evidence from answer citations when snapshot evidence is empty."""
    if not result.answer or not result.answer.citations:
        return result
    snap = dict(result.trajectory_snapshot or {})
    normalized = normalize_trajectory_state(snap)
    if normalized.get("evidence_chunks"):
        return result
    citations = [c.model_dump(mode="json") for c in result.answer.citations]
    normalized["evidence_chunks"] = citations
    if not normalized.get("evidence"):
        normalized["evidence"] = citations
    return result.model_copy(update={"trajectory_snapshot": normalized})


def ungrounded_numeric_tokens(answer_text: str, cited_text: str) -> list[str]:
    """Numeric tokens in answer absent from cited chunk text (warning helper)."""
    if not answer_text.strip():
        return []
    cited = cited_text.lower()
    missing: list[str] = []
    for token in _NUMERIC_TOKEN.findall(answer_text):
        if token.replace(",", "") == "0":
            continue
        if token.lower() not in cited and token.replace(",", "") not in cited:
            missing.append(token)
    return missing


def prepare_result_for_write(result: BenchmarkResult) -> BenchmarkResult:
    """Apply consistency normalization before persisting results.json rows."""
    return ensure_trajectory_citation_consistency(result)
