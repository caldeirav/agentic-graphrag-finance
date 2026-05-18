"""Grounded answer synthesis."""

from __future__ import annotations

import re

from models.enums import QueryStatus, Sufficiency
from models.query import AnswerPackage, EvidenceChunk
from retrieval.orchestration.state import AgentState


def synthesize(state: AgentState) -> dict:
    evidence = state.get("evidence_chunks") or []
    query = state.get("query", "")
    filing_set = state.get("filing_set") or []

    if not evidence or not filing_set:
        return {
            "answer": AnswerPackage(
                text=(
                    "Insufficient evidence in the ingested corpus to answer this question. "
                    f"Required filings or chunks for: {query}"
                ),
                citations=[],
                sufficiency=Sufficiency.INSUFFICIENT,
            ),
            "status": QueryStatus.INSUFFICIENT_EVIDENCE,
        }

    cited_numbers = _extract_numbers_from_evidence(evidence)
    parts = [f"Based on {len(evidence)} evidence chunk(s) from SEC filings:"]
    for i, chunk in enumerate(evidence[:5], 1):
        parts.append(f"[{i}] ({chunk.citation_label}): {chunk.excerpt[:300]}")

    answer_text = "\n".join(parts)
    if cited_numbers:
        answer_text += f"\nReferenced values from source: {', '.join(cited_numbers[:10])}"

    return {
        "answer": AnswerPackage(
            text=answer_text,
            citations=evidence,
            sufficiency=Sufficiency.COMPLETE if len(evidence) >= 1 else Sufficiency.PARTIAL,
        ),
        "status": QueryStatus.SUCCESS,
    }


def _extract_numbers_from_evidence(evidence: list[EvidenceChunk]) -> list[str]:
    numbers: list[str] = []
    for chunk in evidence:
        numbers.extend(re.findall(r"\$?[\d,]+\.?\d*", chunk.excerpt))
    return numbers
