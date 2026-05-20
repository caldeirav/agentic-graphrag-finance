"""Grounded answer synthesis with LLM."""

from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from models.enums import QueryStatus, Sufficiency
from models.filing import FilingRef
from models.query import AnswerPackage, EvidenceChunk
from retrieval.evidence_scope import filter_evidence_for_filing_set
from retrieval.orchestration.llm import create_chat_llm
from retrieval.orchestration.state import AgentState


def synthesize(state: AgentState) -> dict:
    evidence = list(state.get("evidence_chunks") or [])
    query = state.get("query", "")
    filing_set: list[FilingRef] = list(state.get("filing_set") or [])

    if filing_set:
        evidence = filter_evidence_for_filing_set(evidence, filing_set)

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

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _synthesize_template(evidence, query, filing_set)

    return _synthesize_with_llm(evidence, query, filing_set)


def _synthesize_template(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
) -> dict:
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


def _synthesize_with_llm(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list,
) -> dict:
    llm = create_chat_llm()
    period_ends = ", ".join(str(f.period_end) for f in filing_set)
    filing_ctx = json.dumps(
        [
            {
                "form": f.form_type,
                "period_end": str(f.period_end),
                "accession": f.accession,
            }
            for f in filing_set
        ],
        indent=2,
    )
    evidence_block = "\n".join(
        f"[{i}] ({c.citation_label}): {c.excerpt}" for i, c in enumerate(evidence[:15], 1)
    )
    prompt = f"""Answer the financial question using ONLY the SEC filing evidence below.

Filings (use ONLY these — ignore any other period in your training data):
{filing_ctx}

Evidence:
{evidence_block}

Question: {query}

Instructions:
- Give a direct, definitive answer in the first sentence (include dollar amounts and period when present).
- Use XBRL fact lines that match the question (e.g. RevenueFromContractWithCustomer for net sales/revenue).
- The authoritative reporting period end date(s) for this answer: {period_ends}.
- Prefer evidence whose "for period" range ends on that date; do not answer using prior-year comparative periods.
- Do not list raw table IDs; cite fact concepts or filing sections.
- If evidence is insufficient, say so explicitly."""

    resp = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a financial analyst answering from SEC XBRL and filing text. "
                    "Be precise with numbers and periods."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    text = _message_content_to_text(resp.content).strip()
    if not text:
        return _synthesize_template(evidence, query, filing_set)
    return {
        "answer": AnswerPackage(
            text=text,
            citations=evidence[:15],
            sufficiency=Sufficiency.COMPLETE,
        ),
        "status": QueryStatus.SUCCESS,
    }


def _message_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block:
                    parts.append(str(block["text"]))
        return "\n".join(p for p in parts if p)
    return str(content)


def _extract_numbers_from_evidence(evidence: list[EvidenceChunk]) -> list[str]:
    numbers: list[str] = []
    for chunk in evidence:
        numbers.extend(re.findall(r"\$?[\d,]+\.?\d*", chunk.excerpt))
    return numbers
