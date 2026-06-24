"""LLM-guided XBRL fact selection before synthesis (020/021)."""

from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.orchestration.llm import create_chat_llm
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry, is_xbrl_evidence_chunk
from tracing.console_trace.llm import traced_llm_invoke

_XBRL_EXCERPT = re.compile(
    r"XBRL (\w+):\s*(\$[\d,.]+ (?:billion|million|trillion))",
    re.I,
)


class XbrlFactResolutionResult(BaseModel):
    selected_chunk_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    sufficient: bool = True


def _parse_xbrl_line(excerpt: str) -> dict[str, str] | None:
    m = _XBRL_EXCERPT.search(excerpt.strip())
    if not m:
        return None
    return {"concept": m.group(1), "value_text": m.group(2)}


def _year_from_query(query: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", query)]
    return years[0] if years else None


def _mock_resolve_catalog(
    catalog: list[XbrlFactCatalogEntry],
    query: str,
    metric_intent: MetricIntent | None,
) -> XbrlFactResolutionResult:
    target_year = _year_from_query(query)
    best_id = ""
    best_score = -1.0
    for entry in catalog:
        score = 1.0
        if entry.matches_query:
            score += 5.0
        if entry.is_annual:
            score += 3.0
        if target_year and str(target_year) in entry.period_end:
            score += 8.0
        if metric_intent and metric_intent.periods_needed >= 2 and entry.is_annual:
            score += 2.0
        if score > best_score:
            best_score = score
            best_id = entry.chunk_id
    if metric_intent and metric_intent.periods_needed >= 2:
        annual = sorted(
            [e for e in catalog if e.is_annual or (target_year and str(target_year) in e.period_end)],
            key=lambda e: e.period_end,
            reverse=True,
        )
        ids = [e.chunk_id for e in annual[:2]]
        if len(ids) >= 2:
            return XbrlFactResolutionResult(
                selected_chunk_ids=ids,
                rationale="Mock: top two annual facts for computation.",
                sufficient=True,
            )
    if not best_id and catalog:
        best_id = catalog[0].chunk_id
    return XbrlFactResolutionResult(
        selected_chunk_ids=[best_id] if best_id else [],
        rationale="Mock: heuristic catalog match.",
        sufficient=bool(best_id),
    )


def resolve_xbrl_facts_from_catalog(
    catalog: list[XbrlFactCatalogEntry],
    query: str,
    filing_set: list[FilingRef],
    *,
    fiscal_period_hints: list[str] | None = None,
    metric_intent: MetricIntent | None = None,
    temporal_intent=None,
) -> tuple[XbrlFactResolutionResult, dict]:
    if not catalog:
        return (
            XbrlFactResolutionResult(
                selected_chunk_ids=[],
                rationale="Empty XBRL catalog.",
                sufficient=False,
            ),
            {},
        )
    if metric_intent and metric_intent.metric_type == "ratio" and metric_intent.periods_needed == 1:
        from retrieval.skills.ratio_pair_resolution import ratio_pair_to_resolution, resolve_ratio_pair

        pair = resolve_ratio_pair(
            catalog,
            metric_intent,
            query,
            temporal_intent=temporal_intent,
        )
        return ratio_pair_to_resolution(pair), {}
    if len(catalog) == 1:
        return (
            XbrlFactResolutionResult(
                selected_chunk_ids=[catalog[0].chunk_id],
                rationale="Single catalog entry.",
                sufficient=True,
            ),
            {},
        )
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _mock_resolve_catalog(catalog, query, metric_intent), {}

    facts = [entry.model_dump() for entry in catalog[:20]]
    hint_line = ""
    if fiscal_period_hints:
        hint_line = f"Prefer periods matching: {', '.join(fiscal_period_hints)}.\n"
    metric_line = ""
    if metric_intent:
        metric_line = (
            f"Metric type: {metric_intent.metric_type}; periods_needed="
            f"{metric_intent.periods_needed}.\n"
        )

    prompt = (
        f"Question: {query}\n"
        f"{hint_line}"
        f"{metric_line}"
        f"XBRL catalog (JSON): {json.dumps(facts, indent=2)}\n"
        "Return JSON: "
        '{"selected_chunk_ids": [str], "rationale": str, "sufficient": bool}\n'
        "Select fact(s) matching metric AND period. For delta/ratio/% select multiple ids."
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
        return _mock_resolve_catalog(catalog, query, metric_intent), trace_patch
    try:
        result = XbrlFactResolutionResult.model_validate(data)
    except Exception:
        ids = [str(i) for i in (data.get("selected_chunk_ids") or [])]
        result = XbrlFactResolutionResult(
            selected_chunk_ids=ids,
            rationale=str(data.get("rationale") or ""),
            sufficient=bool(data.get("sufficient", True)),
        )
    if not result.selected_chunk_ids:
        result = result.model_copy(
            update={"selected_chunk_ids": [catalog[0].chunk_id], "sufficient": False}
        )
    return result, trace_patch


def resolve_xbrl_facts(
    xbrl_chunks: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    fiscal_period_hints: list[str] | None = None,
    metric_intent: MetricIntent | None = None,
    catalog: list[XbrlFactCatalogEntry] | None = None,
) -> tuple[XbrlFactResolutionResult, dict]:
    if catalog is not None:
        return resolve_xbrl_facts_from_catalog(
            catalog,
            query,
            filing_set,
            fiscal_period_hints=fiscal_period_hints,
            metric_intent=metric_intent,
        )
    from retrieval.skills.xbrl_fact_catalog import build_xbrl_fact_catalog

    built = build_xbrl_fact_catalog(xbrl_chunks, query, filing_set)
    if built:
        return resolve_xbrl_facts_from_catalog(
            built,
            query,
            filing_set,
            fiscal_period_hints=fiscal_period_hints,
            metric_intent=metric_intent,
        )
    if not xbrl_chunks:
        return (
            XbrlFactResolutionResult(selected_chunk_ids=[], rationale="No XBRL.", sufficient=False),
            {},
        )
    return (
        XbrlFactResolutionResult(
            selected_chunk_ids=[xbrl_chunks[0].chunk_node_id],
            rationale="Fallback first XBRL chunk.",
            sufficient=True,
        ),
        {},
    )


def filter_evidence_by_resolution(
    evidence: list[EvidenceChunk],
    resolution: XbrlFactResolutionResult,
) -> list[EvidenceChunk]:
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
