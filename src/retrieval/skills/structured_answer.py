"""Structured answer contract for live synthesis (020)."""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models.enums import QueryIntent, QueryStatus, Sufficiency
from models.filing import FilingRef
from models.query import AnswerPackage, EvidenceChunk
from retrieval.context_budget import compact_evidence_for_llm, trim_prompt_text
from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.orchestration.llm import create_chat_llm
from retrieval.orchestration.state import AgentState
from tracing.console_trace.llm import traced_llm_invoke

CHUNK_DUMP_PATTERN = re.compile(
    r"^Based on \d+ evidence chunk",
    re.IGNORECASE | re.MULTILINE,
)


class StructuredAnswerPayload(BaseModel):
    metric_label: str
    value: str
    unit: str = ""
    fiscal_period: str = ""
    concept: str = ""
    citation_chunk_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    abstain: bool = False
    abstain_reason: str = ""
    metric_type: Literal["point", "delta", "ratio", "percent_change"] = "point"
    inputs: list[dict] = Field(default_factory=list)
    formula: str = ""
    computed_value: str = ""


def is_chunk_dump_answer(text: str) -> bool:
    return bool(CHUNK_DUMP_PATTERN.search(text.strip()))


def render_structured_answer(payload: StructuredAnswerPayload) -> str:
    if payload.abstain:
        reason = payload.abstain_reason.strip() or "Evidence does not contain the requested metric."
        return f"Insufficient evidence: {reason}"
    parts = [payload.value]
    if payload.unit:
        parts[0] = f"{payload.value} {payload.unit}".strip()
    lead = f"{payload.metric_label} was {parts[0]}"
    if payload.fiscal_period:
        lead += f" for {payload.fiscal_period}"
    if payload.concept:
        lead += f" (XBRL {payload.concept})"
    lead += "."
    if payload.formula and payload.computed_value:
        lead += f" Computed as {payload.formula}: {payload.computed_value}."
    if payload.confidence != "high":
        lead += f" Confidence: {payload.confidence}."
    return lead


def _benchmark_fiscal_guidance(state: AgentState | None) -> str:
    if not state:
        return ""
    raw = str(state.get("fiscal_period_labels_json") or "[]")
    try:
        labels = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(labels, list) or not labels:
        return ""
    joined = ", ".join(str(label) for label in labels)
    return (
        f"Benchmark fiscal period hint — prefer XBRL facts whose period matches: {joined}."
    )


def _parse_structured_payload(data: dict) -> StructuredAnswerPayload | None:
    if not data:
        return None
    try:
        return StructuredAnswerPayload.model_validate(data)
    except Exception:
        return None


def synthesize_structured_answer(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    temporal_anchor: str = "",
    state: AgentState | None = None,
    budget: dict[str, int] | None = None,
) -> tuple[StructuredAnswerPayload | None, dict]:
    """LLM JSON structured answer; returns payload and trace patch."""
    llm = create_chat_llm()
    intent_trace = state.get("intent_trace") if isinstance(state, dict) else None
    query_intent = intent_trace.query_intent if intent_trace else None
    qualitative = query_intent == QueryIntent.QUALITATIVE
    prompt_evidence = compact_evidence_for_llm(
        evidence,
        query=query,
        query_intent=query_intent,
        budget=budget,
    )
    evidence_block = "\n".join(
        f"id={c.chunk_node_id} [{getattr(c.source_type, 'value', c.source_type)}] "
        f"({c.citation_label}): {c.excerpt}"
        for c in prompt_evidence
    )
    period_ends = ", ".join(str(f.period_end) for f in filing_set)
    fiscal_hint = _benchmark_fiscal_guidance(state)
    temporal_line = ""
    if temporal_anchor.strip():
        temporal_line = f"Temporal anchor: {temporal_anchor.strip()}."
    instructions = (
        "Return ONLY JSON matching this schema:\n"
        '{"metric_label": str, "value": str, "unit": str, "fiscal_period": str, '
        '"concept": str, "citation_chunk_ids": [str], "confidence": "high|medium|low", '
        '"abstain": bool, "abstain_reason": str}\n'
        "- First sentence of rendered answer must state one definitive numeric or ratio claim.\n"
        "- Never list raw evidence chunks or say 'Based on N evidence chunk(s)'.\n"
        "- Use citation_chunk_ids from the evidence id= fields only.\n"
        "- Set abstain=true if the bound period lacks the requested metric.\n"
    )
    if qualitative:
        instructions += "- Qualitative question: metric_label may describe the theme; value summarizes finding.\n"
    else:
        instructions += (
            "- Numeric question: value must be the figure from XBRL (e.g. $416.16 billion).\n"
            f"- Bound period end date(s): {period_ends}.\n"
        )
    if fiscal_hint:
        instructions += f"- {fiscal_hint}\n"
    if temporal_line:
        instructions += f"- {temporal_line}\n"

    prompt = trim_prompt_text(
        f"""Answer using ONLY the evidence below.

Evidence:
{evidence_block}

Question: {query}

{instructions}""",
        budget=budget,
    )
    messages = [
        SystemMessage(
            content=(
                "You are a financial analyst. Output strict JSON only—no markdown, no prose."
            )
        ),
        HumanMessage(content=prompt),
    ]
    resp, trace_patch = traced_llm_invoke("synthesize_structured", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    payload = _parse_structured_payload(extract_json_from_llm(text))
    return payload, trace_patch


def structured_synthesis_result(
    payload: StructuredAnswerPayload,
    evidence: list[EvidenceChunk],
    *,
    trace_patch: dict | None = None,
) -> dict:
    text = render_structured_answer(payload)
    id_set = set(payload.citation_chunk_ids)
    cites = [c for c in evidence if c.chunk_node_id in id_set] if id_set else evidence[:3]
    if not cites:
        cites = evidence[:3]
    status = (
        QueryStatus.INSUFFICIENT_EVIDENCE if payload.abstain else QueryStatus.SUCCESS
    )
    sufficiency = Sufficiency.INSUFFICIENT if payload.abstain else Sufficiency.COMPLETE
    out = {
        "answer": AnswerPackage(text=text, citations=cites, sufficiency=sufficiency),
        "status": status,
    }
    if trace_patch and trace_patch.get("trace_events"):
        out["trace_events"] = trace_patch["trace_events"]
    return out
