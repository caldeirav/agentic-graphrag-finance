"""LLM-guided XBRL fact selection before synthesis (020)."""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.orchestration.llm import create_chat_llm
from tracing.console_trace.llm import traced_llm_invoke

_XBRL_EXCERPT = re.compile(
    r"XBRL (\w+):\s*(\$[\d,.]+ (?:billion|million|trillion))",
    re.I,
)


class XbrlFactResolutionResult(BaseModel):
    selected_chunk_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    sufficient: bool = True


def is_xbrl_evidence_chunk(chunk: EvidenceChunk) -> bool:
    src = getattr(chunk.source_type, "value", str(chunk.source_type))
    if "XBRL" in src.upper():
        return True
    if "XBRL" in (chunk.section_id or "").upper():
        return True
    return "XBRL" in chunk.excerpt[:40].upper()


def _parse_xbrl_line(excerpt: str) -> dict[str, str] | None:
    m = _XBRL_EXCERPT.search(excerpt.strip())
    if not m:
        return None
    return {"concept": m.group(1), "value_text": m.group(2)}


def _year_from_query(query: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", query)]
    return years[0] if years else None


def _mock_resolve(
    xbrl_chunks: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
) -> XbrlFactResolutionResult:
    target_year = _year_from_query(query)
    if not target_year and filing_set:
        annual = [f for f in filing_set if f.form_type.upper() == "10-K"]
        if len(annual) == 1:
            target_year = annual[0].period_end.year
    best_id = ""
    best_score = -1.0
    for chunk in xbrl_chunks:
        parsed = _parse_xbrl_line(chunk.excerpt)
        if not parsed:
            continue
        score = 1.0
        if target_year and str(target_year) in chunk.excerpt:
            score += 5.0
        q = query.lower()
        concept = parsed["concept"].lower()
        if "revenue" in q and "revenue" in concept:
            score += 3.0
        if "equity" in q and "equity" in concept:
            score += 3.0
        if score > best_score:
            best_score = score
            best_id = chunk.chunk_node_id
    if not best_id:
        return XbrlFactResolutionResult(
            selected_chunk_ids=[c.chunk_node_id for c in xbrl_chunks[:1]],
            rationale="Mock: no scored match; kept top XBRL chunk.",
            sufficient=True,
        )
    return XbrlFactResolutionResult(
        selected_chunk_ids=[best_id],
        rationale="Mock: heuristic XBRL fact match.",
        sufficient=True,
    )


def resolve_xbrl_facts(
    xbrl_chunks: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    fiscal_period_hints: list[str] | None = None,
) -> tuple[XbrlFactResolutionResult, dict]:
    """Select XBRL facts matching the question; returns result and trace patch."""
    import os

    if not xbrl_chunks:
        return (
            XbrlFactResolutionResult(
                selected_chunk_ids=[],
                rationale="No XBRL evidence.",
                sufficient=False,
            ),
            {},
        )
    if len(xbrl_chunks) == 1:
        return (
            XbrlFactResolutionResult(
                selected_chunk_ids=[xbrl_chunks[0].chunk_node_id],
                rationale="Single XBRL fact in evidence.",
                sufficient=True,
            ),
            {},
        )
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _mock_resolve(xbrl_chunks, query, filing_set), {}

    facts = []
    for chunk in xbrl_chunks:
        parsed = _parse_xbrl_line(chunk.excerpt) or {}
        facts.append(
            {
                "chunk_id": chunk.chunk_node_id,
                "concept": parsed.get("concept", ""),
                "value": parsed.get("value_text", ""),
                "excerpt": chunk.excerpt[:400],
            }
        )
    hint_line = ""
    if fiscal_period_hints:
        hint_line = f"Prefer periods matching: {', '.join(fiscal_period_hints)}.\n"

    prompt = (
        f"Question: {query}\n"
        f"{hint_line}"
        f"XBRL facts (JSON): {json.dumps(facts, indent=2)}\n"
        "Return JSON: "
        '{"selected_chunk_ids": [str], "rationale": str, "sufficient": bool}\n'
        "Select the fact(s) that answer the question metric and period. "
        "For ratios you may select multiple ids. Set sufficient=false if none match."
    )
    llm = create_chat_llm()
    messages = [
        SystemMessage(content="You select SEC XBRL facts for financial QA. JSON only."),
        HumanMessage(content=prompt),
    ]
    resp, trace_patch = traced_llm_invoke("xbrl_fact_resolution", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    data = extract_json_from_llm(text)
    if not data:
        return (
            XbrlFactResolutionResult(
                selected_chunk_ids=[xbrl_chunks[0].chunk_node_id],
                rationale="Resolution parse failed; kept first XBRL chunk.",
                sufficient=True,
            ),
            trace_patch,
        )
    try:
        result = XbrlFactResolutionResult.model_validate(data)
    except Exception:
        ids = list(data.get("selected_chunk_ids") or [])
        result = XbrlFactResolutionResult(
            selected_chunk_ids=[str(i) for i in ids],
            rationale=str(data.get("rationale") or ""),
            sufficient=bool(data.get("sufficient", True)),
        )
    if not result.selected_chunk_ids:
        result = result.model_copy(
            update={
                "selected_chunk_ids": [xbrl_chunks[0].chunk_node_id],
                "sufficient": False,
            }
        )
    return result, trace_patch


def filter_evidence_by_resolution(
    evidence: list[EvidenceChunk],
    resolution: XbrlFactResolutionResult,
) -> list[EvidenceChunk]:
    """Keep non-XBRL chunks plus selected XBRL chunks."""
    selected = set(resolution.selected_chunk_ids)
    out: list[EvidenceChunk] = []
    for chunk in evidence:
        if is_xbrl_evidence_chunk(chunk):
            if chunk.chunk_node_id in selected:
                out.append(chunk)
        else:
            out.append(chunk)
    if not any(is_xbrl_evidence_chunk(c) for c in out) and resolution.selected_chunk_ids:
        by_id = {c.chunk_node_id: c for c in evidence}
        for cid in resolution.selected_chunk_ids:
            if cid in by_id:
                out.append(by_id[cid])
    return out or list(evidence)
