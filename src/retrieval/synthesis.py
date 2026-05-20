"""Grounded answer synthesis with LLM."""

from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from models.corpus import FiscalPeriodLabel, infer_fiscal_year_end_month
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

    temporal_anchor = str(state.get("temporal_anchor") or "")

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _synthesize_template(
            evidence, query, filing_set, temporal_anchor=temporal_anchor
        )

    return _synthesize_with_llm(evidence, query, filing_set, temporal_anchor=temporal_anchor)


def _synthesize_template(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    temporal_anchor: str = "",
) -> dict:
    period_ends = ", ".join(str(f.period_end) for f in filing_set)
    revenue_line = _best_revenue_excerpt(evidence, filing_set)
    if revenue_line and _normalize_anchor(temporal_anchor) in (
        "prior_quarter",
        "previous_quarter",
        "latest_quarter",
        "latest_q",
    ):
        answer_text = (
            f"Revenue for the bound period (period end {period_ends}) was {revenue_line} "
            f"(from SEC XBRL evidence)."
        )
    else:
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


def _normalize_anchor(anchor: str) -> str:
    return anchor.strip().lower().replace("-", "_")


def _temporal_synthesis_guidance(
    temporal_anchor: str,
    filing_set: list[FilingRef],
    *,
    period_ends: str,
) -> str:
    anchor = _normalize_anchor(temporal_anchor)
    fy_end = infer_fiscal_year_end_month(filing_set) if filing_set else 12
    labels = [
        FiscalPeriodLabel.from_filing(f, fiscal_year_end_month=fy_end).label
        for f in filing_set
    ]
    label_text = ", ".join(labels) if labels else "n/a"

    if anchor in ("prior_quarter", "previous_quarter"):
        return (
            f"Temporal scope: prior fiscal quarter ({label_text}). The bound filing(s) ARE that "
            f"quarter relative to the newest 10-Q in the corpus—not the latest quarter. "
            f"Report revenue using XBRL facts whose period ends on {period_ends} (or whose "
            f"'for period' range ends within a few days of that date). "
            f"If evidence shows revenue for that period, state it as the answer; do not refuse "
            f"because the question says 'prior quarter' or because YoY comparative periods also "
            f"appear in the filing."
        )
    if anchor in ("latest_quarter", "latest_q"):
        return (
            f"Temporal scope: latest fiscal quarter ({label_text}). "
            f"Use facts for period ending {period_ends}."
        )
    if anchor in ("latest_annual", "latest_annual_report"):
        return (
            f"Temporal scope: latest annual report ({label_text}). "
            f"Use facts for period ending {period_ends}."
        )
    return (
        f"Bound reporting period end date(s): {period_ends}. "
        f"Prefer evidence whose 'for period' range ends on that date."
    )


def _synthesize_with_llm(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list,
    *,
    temporal_anchor: str = "",
) -> dict:
    llm = create_chat_llm()
    period_ends = ", ".join(str(f.period_end) for f in filing_set)
    fy_end = infer_fiscal_year_end_month(filing_set) if filing_set else 12
    filing_ctx = json.dumps(
        [
            {
                "form": f.form_type,
                "fiscal_period": FiscalPeriodLabel.from_filing(
                    f, fiscal_year_end_month=fy_end
                ).label,
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
    temporal_guidance = _temporal_synthesis_guidance(
        temporal_anchor, filing_set, period_ends=period_ends
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
- {temporal_guidance}
- Ignore prior-year comparative XBRL periods unless the question explicitly asks for year-over-year comparison.
- Do not list raw table IDs; cite fact concepts or filing sections.
- If no evidence matches the bound period, say so explicitly."""

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
        return _synthesize_template(
            evidence, query, filing_set, temporal_anchor=temporal_anchor
        )
    return {
        "answer": AnswerPackage(
            text=text,
            citations=evidence[:15],
            sufficiency=Sufficiency.COMPLETE,
        ),
        "status": QueryStatus.SUCCESS,
    }


def _best_revenue_excerpt(
    evidence: list[EvidenceChunk],
    filing_set: list[FilingRef],
) -> str:
    """Prefer aligned RevenueFromContract excerpt for template/mock answers."""
    from retrieval.evidence_scope import anchor_period_ends, period_matches_anchor

    anchors = anchor_period_ends(filing_set)
    best: tuple[float, str] | None = None
    for chunk in evidence:
        ex = chunk.excerpt
        if "RevenueFromContract" not in ex and "revenue" not in ex.lower():
            continue
        if not period_matches_anchor(None, anchors, excerpt=ex):
            continue
        m = re.search(r"\$[\d,.]+ (?:billion|million)", ex, re.I)
        if not m:
            continue
        score = 10.0 if "RevenueFromContract" in ex else 5.0
        if best is None or score > best[0]:
            best = (score, m.group(0))
    return best[1] if best else ""


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
