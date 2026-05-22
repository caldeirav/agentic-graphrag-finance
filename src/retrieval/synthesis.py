"""Grounded answer synthesis with LLM."""

from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from models.corpus import FiscalPeriodLabel, infer_fiscal_year_end_month
from models.enums import QueryIntent, QueryStatus, Sufficiency
from models.filing import FilingRef
from models.query import AnswerPackage, EvidenceChunk
from retrieval.context_budget import (
    budget_for_context_error,
    compact_evidence_for_llm,
    is_context_length_error,
    trim_prompt_text,
)
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
            evidence,
            query,
            filing_set,
            temporal_anchor=temporal_anchor,
            state=state,
        )

    try:
        return _synthesize_with_llm(
            evidence,
            query,
            filing_set,
            temporal_anchor=temporal_anchor,
            state=state,
        )
    except Exception as exc:
        if not is_context_length_error(exc):
            raise
        fallback = budget_for_context_error(exc)
        if fallback is None:
            raise
        return _synthesize_with_llm(
            evidence,
            query,
            filing_set,
            temporal_anchor=temporal_anchor,
            state=state,
            budget=fallback,
        )


def _synthesize_template(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    temporal_anchor: str = "",
    state: AgentState | None = None,
) -> dict:
    period_ends = ", ".join(str(f.period_end) for f in filing_set)
    intent_trace = (state or {}).get("intent_trace") if state else None
    if intent_trace and intent_trace.query_intent == QueryIntent.QUALITATIVE:
        html_chunks = [c for c in evidence if "HTML" in str(getattr(c.source_type, "value", c.source_type))]
        if html_chunks:
            if "risk" in query.lower():
                risk_chunks = [
                    c
                    for c in html_chunks
                    if "risk" in c.excerpt.lower() or "risk" in (c.section_id or "").lower()
                ]
                lead_chunk = (
                    max(risk_chunks, key=lambda c: len(c.excerpt)) if risk_chunks else html_chunks[0]
                )
            else:
                lead_chunk = max(html_chunks, key=lambda c: len(c.excerpt))
            lead = lead_chunk.excerpt[:1200]
            return {
                "answer": AnswerPackage(
                    text=(
                        "Principal risk factors from the bound filing narrative (HTML excerpt): "
                        f"{lead}..."
                    ),
                    citations=html_chunks[:5],
                    sufficiency=Sufficiency.COMPLETE,
                ),
                "status": QueryStatus.SUCCESS,
            }
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
            src = getattr(chunk.source_type, "value", str(chunk.source_type))
            parts.append(f"[{i}] [{src}] ({chunk.citation_label}): {chunk.excerpt[:300]}")
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
    state: AgentState | None = None,
    budget: dict[str, int] | None = None,
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
    intent_trace = state.get("intent_trace") if isinstance(state, dict) else None
    qualitative = (
        intent_trace is not None and intent_trace.query_intent == QueryIntent.QUALITATIVE
    )
    query_intent = intent_trace.query_intent if intent_trace else None
    prompt_evidence = compact_evidence_for_llm(
        evidence,
        query=query,
        query_intent=query_intent,
        budget=budget,
    )
    evidence_block = "\n".join(
        f"[{i}] [{getattr(c.source_type, 'value', c.source_type)}] ({c.citation_label}): {c.excerpt}"
        for i, c in enumerate(prompt_evidence, 1)
    )
    temporal_guidance = _temporal_synthesis_guidance(
        temporal_anchor, filing_set, period_ends=period_ends
    )
    if qualitative:
        instructions = (
            "- Answer from HTML narrative excerpts (Item 1A risk factors, MD&A, business description).\n"
            "- Summarize principal risks in prose; do not reply with only XBRL numeric facts.\n"
            "- Prefer the annual report (10-K) when multiple filings are bound.\n"
            "- If risk-factor narrative is present in evidence, extract and list the main themes.\n"
            "- If evidence lacks narrative risk discussion, say so explicitly."
        )
        system = (
            "You are a financial analyst answering from SEC filing narrative (HTML) sections. "
            "Focus on qualitative disclosures, not taxonomy numbers."
        )
    else:
        instructions = (
            "- Give a direct, definitive answer in the first sentence (include dollar amounts and period when present).\n"
            "- Use XBRL fact lines that match the question (e.g. RevenueFromContractWithCustomer for net sales/revenue).\n"
            f"- {temporal_guidance}\n"
            "- Ignore prior-year comparative XBRL periods unless the question explicitly asks for year-over-year comparison.\n"
            "- Do not list raw table IDs; cite fact concepts or filing sections.\n"
            "- If no evidence matches the bound period, say so explicitly."
        )
        system = (
            "You are a financial analyst answering from SEC XBRL and filing text. "
            "Be precise with numbers and periods."
        )

    prompt = trim_prompt_text(
        f"""Answer the financial question using ONLY the SEC filing evidence below.

Filings (use ONLY these — ignore any other period in your training data):
{filing_ctx}

Evidence:
{evidence_block}

Question: {query}

Instructions:
{instructions}""",
        budget=budget,
    )

    resp = llm.invoke(
        [
            SystemMessage(content=system),
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
            citations=evidence[: len(prompt_evidence)],
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
