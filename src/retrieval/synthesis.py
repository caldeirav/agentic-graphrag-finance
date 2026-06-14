"""Grounded answer synthesis with LLM."""

from __future__ import annotations

import json
import os
import re
from datetime import date

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
from retrieval.evidence_scope import (
    filter_evidence_for_filing_set,
    parse_period_end_from_excerpt,
    period_matches_anchor,
)
from retrieval.orchestration.llm import create_chat_llm
from retrieval.orchestration.micro_scoring import excerpt_topic_score, rank_evidence_by_topic
from retrieval.orchestration.meso_scoring import is_risk_only_query
from retrieval.orchestration.state import AgentState
from tracing.console_trace.llm import traced_llm_invoke


def _yoy_comparison_intent(query: str, state: AgentState | None) -> bool:
    q = query.lower()
    yoy = any(
        k in q
        for k in ("year over year", "year-over-year", "yoy", "compared to last year")
    )
    if not state:
        return yoy
    filing_set = list(state.get("filing_set") or [])
    multi_filing = len(filing_set) >= 2
    macro = state.get("macro_plan")
    if macro and getattr(macro.temporal_scope, "comparison_mode", None):
        from models.enums import ComparisonMode

        if multi_filing:
            yoy = yoy or macro.temporal_scope.comparison_mode == ComparisonMode.YOY
    record = state.get("macro_binding_record")
    if record and getattr(record, "validation", None):
        from models.enums import ComparisonMode

        if multi_filing:
            yoy = yoy or record.validation.comparison_mode == ComparisonMode.YOY
    return yoy


def _yoy_intra_filing_10k(
    state: AgentState | None,
    query: str,
    filing_set: list[FilingRef],
) -> bool:
    return (
        len(filing_set) == 1
        and filing_set[0].form_type == "10-K"
        and _yoy_comparison_intent(query, state)
    )


def _tag_synthesis_path(result: dict, path: str) -> dict:
    out = dict(result)
    out["synthesis_path"] = path
    if path == "deterministic_fallback":
        out["synthesis_yoy_fallback"] = True
    return out


def synthesize(state: AgentState) -> dict:
    if state.get("macro_binding_failed") and state.get("answer") is not None:
        return {
            "answer": state["answer"],
            "status": state.get("status", QueryStatus.ERROR),
        }

    evidence = list(state.get("evidence_chunks") or [])
    query = state.get("query", "")
    filing_set: list[FilingRef] = list(state.get("filing_set") or [])

    if filing_set:
        evidence = filter_evidence_for_filing_set(
            evidence,
            filing_set,
            include_comparative_periods=_yoy_intra_filing_10k(state, query, filing_set),
        )

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

    temporal_anchor = _resolve_temporal_anchor(state)

    comparison_risk = _try_synthesize_comparison_risk(evidence, query, filing_set)
    if comparison_risk is not None:
        return _tag_synthesis_path(comparison_risk, "comparison_risk_deterministic")

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _tag_synthesis_path(
            _synthesize_template(
                evidence,
                query,
                filing_set,
                temporal_anchor=temporal_anchor,
                state=state,
            ),
            "template",
        )

    try:
        return _tag_synthesis_path(
            _synthesize_with_llm(
                evidence,
                query,
                filing_set,
                temporal_anchor=temporal_anchor,
                state=state,
            ),
            "live_llm",
        )
    except Exception as exc:
        if not is_context_length_error(exc):
            raise
        fallback = budget_for_context_error(exc)
        if fallback is None:
            raise
        result = _synthesize_with_llm(
            evidence,
            query,
            filing_set,
            temporal_anchor=temporal_anchor,
            state=state,
            budget=fallback,
        )
        result["synthesis_retry_budget"] = True
        return _tag_synthesis_path(result, "live_llm")


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
        yoy_text = _synthesize_yoy_net_sales(evidence, filing_set, query, state=state)
        if yoy_text:
            answer_text = yoy_text
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


def _resolve_temporal_anchor(state: AgentState) -> str:
    """CLI anchor, macro proposal anchor, or query phrase inference for synthesis."""
    anchor = str(state.get("temporal_anchor") or "").strip()
    if anchor:
        return anchor
    record = state.get("macro_binding_record")
    if record is not None:
        proposal = getattr(record, "proposal", None)
        if proposal and getattr(proposal, "anchor", None):
            return str(proposal.anchor)
    query = str(state.get("query") or "")
    from retrieval.macro.pairing import infer_anchor_from_query

    inferred = infer_anchor_from_query(query)
    return inferred or ""


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
    q = ""
    if len(filing_set) == 1 and filing_set[0].form_type.upper() == "10-Q":
        q = (
            f" Single 10-Q bound ({label_text}, period end {period_ends}). "
            f"If the question names 'prior quarter' or 'latest quarter', that phrase refers to "
            f"this bound quarter relative to newer filings in the corpus—not a missing period."
        )
    return (
        f"Bound reporting period end date(s): {period_ends}. "
        f"Prefer evidence whose 'for period' range ends on that date.{q}"
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
    anti_abstain = (
        "- When evidence excerpts are present and on-topic, provide your best direct answer; "
        "do not refuse with 'cannot identify' or 'cannot answer' unless evidence is empty or wrong issuer.\n"
    )
    if qualitative:
        instructions = (
            anti_abstain
            + "- Answer from HTML narrative excerpts (Item 1A risk factors, MD&A, business description).\n"
            + (
                "- This is a cross-filing comparison: address EACH bound company/filing separately, "
                "then state similarities or differences.\n"
                if _is_comparison_query(query) and len(filing_set) >= 2
                else ""
            )
            + "- Summarize principal risks in prose; do not reply with only XBRL numeric facts.\n"
            "- Prefer the annual report (10-K) when multiple filings are bound.\n"
            "- If risk-factor narrative is present in evidence, extract and list the main themes.\n"
            "- If evidence lacks narrative risk discussion, say so explicitly."
        )
        system = (
            "You are a financial analyst answering from SEC filing narrative (HTML) sections. "
            "Focus on qualitative disclosures, not taxonomy numbers."
        )
    else:
        yoy_query = _yoy_comparison_intent(query, state)
        yoy_extra = ""
        if yoy_query and len(filing_set) >= 2:
            yoy_extra = (
                "- This is a year-over-year comparison: use RevenueFromContractWithCustomer "
                "(or equivalent net sales/revenue) from EACH bound annual filing, one figure per "
                "fiscal year, then state the change.\n"
            )
        elif yoy_query and _yoy_intra_filing_10k(state, query, filing_set):
            yoy_extra = (
                "- This is a year-over-year comparison within one 10-K: use current and prior "
                "fiscal year RevenueFromContractWithCustomer (net sales) from the comparative "
                "XBRL periods in the evidence, then state the change.\n"
            )
        ignore_prior = (
            ""
            if yoy_query
            else (
                "- Ignore prior-year comparative XBRL periods unless the question explicitly "
                "asks for year-over-year comparison.\n"
            )
        )
        instructions = (
            anti_abstain
            + "- Give a direct, definitive answer in the first sentence (include dollar amounts and period when present).\n"
            "- Use XBRL fact lines that match the question (e.g. RevenueFromContractWithCustomer for net sales/revenue).\n"
            f"- {temporal_guidance}\n"
            f"{yoy_extra}"
            f"{ignore_prior}"
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

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ]
    resp, trace_patch = traced_llm_invoke("synthesize", llm, messages)
    text = _response_text(resp).strip()
    if not text:
        yoy_text = _synthesize_yoy_net_sales(
            evidence, filing_set, query, state=state
        )
        if yoy_text:
            out = {
                "answer": AnswerPackage(
                    text=yoy_text,
                    citations=evidence[: len(prompt_evidence)],
                    sufficiency=Sufficiency.COMPLETE,
                ),
                "status": QueryStatus.SUCCESS,
                "synthesis_fallback": "yoy_deterministic",
            }
            if trace_patch.get("trace_events"):
                out["trace_events"] = trace_patch["trace_events"]
            return out
        return _synthesize_template(
            evidence,
            query,
            filing_set,
            temporal_anchor=temporal_anchor,
            state=state,
        )
    text = _correct_revenue_denial(
        text,
        query=query,
        evidence=evidence,
        filing_set=filing_set,
        temporal_anchor=temporal_anchor,
        period_ends=period_ends,
        state=state,
    )
    text = _correct_abstention_denial(
        text,
        query=query,
        evidence=evidence,
        filing_set=filing_set,
        state=state,
    )
    out = {
        "answer": AnswerPackage(
            text=text,
            citations=evidence[: len(prompt_evidence)],
            sufficiency=Sufficiency.COMPLETE,
        ),
        "status": QueryStatus.SUCCESS,
    }
    if trace_patch.get("trace_events"):
        out["trace_events"] = trace_patch["trace_events"]
    return out


def _is_comparison_query(query: str) -> bool:
    q = query.lower()
    return any(
        k in q
        for k in ("compare", "comparison", "versus", " vs ", "both companies", "both filings", "across", "contrast")
    )


def _is_risk_comparison_query(query: str) -> bool:
    return _is_comparison_query(query) and (
        is_risk_only_query(query) or "geopolitic" in query.lower() or "international" in query.lower()
    )


def _risk_topic_phrase(query: str) -> str:
    q = query.lower()
    if "geopolitic" in q and "international" in q:
        return "international operations and geopolitical instability"
    if "trade" in q or "tariff" in q:
        return "international trade policies and geopolitical instability"
    if "conflict" in q or "war" in q:
        return "international conflicts and geopolitical instability"
    return "material risks and uncertainties"


def _extract_risk_sentences(excerpt: str, query: str, *, max_sentences: int = 2) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", excerpt.replace("\n", " "))
    scored: list[tuple[float, str]] = []
    for sentence in sentences:
        text = sentence.strip()
        if len(text) < 50:
            continue
        score = excerpt_topic_score(query, text, "")
        if score <= 0 and "risk" not in text.lower():
            continue
        scored.append((score, text))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _, text in scored[:max_sentences]]


def _chunks_for_filing(evidence: list[EvidenceChunk], filing: FilingRef) -> list[EvidenceChunk]:
    acc = filing.accession
    doc_prefix = f"doc-{acc}"
    return [
        c
        for c in evidence
        if c.accession == acc or (c.chunk_node_id or "").startswith(doc_prefix)
    ]


def _try_synthesize_comparison_risk(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
) -> dict | None:
    """Deterministic comparison answer for multi-filing risk-factor questions."""
    if not _is_risk_comparison_query(query) or len(filing_set) < 2:
        return None
    topic = _risk_topic_phrase(query)
    issuer_labels = [f"{f.form_type} ({f.accession})" for f in filing_set[:2]]
    header = (
        f"Both {issuer_labels[0]} and {issuer_labels[1]} discuss risks related to "
        f"{topic} in Item 1A. Risk Factors."
    )
    body_lines: list[str] = []
    citations: list[EvidenceChunk] = []
    for filing in filing_set[:2]:
        pool = rank_evidence_by_topic(_chunks_for_filing(evidence, filing), query, max_chunks=4)
        if not pool:
            continue
        sentences = _extract_risk_sentences(pool[0].excerpt, query)
        if sentences:
            body_lines.append(
                f"In {filing.form_type} ({filing.accession}): " + " ".join(sentences)
            )
        else:
            preview = pool[0].excerpt[:400].strip()
            body_lines.append(f"In {filing.form_type} ({filing.accession}): {preview}...")
        citations.extend(pool[:2])
    if len(body_lines) < 1:
        return None
    text = header
    if body_lines:
        text = header + "\n\n" + "\n".join(body_lines)
    return {
        "answer": AnswerPackage(
            text=text,
            citations=citations[:8],
            sufficiency=Sufficiency.COMPLETE,
        ),
        "status": QueryStatus.SUCCESS,
    }


def _looks_like_refusal(text: str) -> bool:
    lower = text.lower()
    return any(
        p in lower
        for p in (
            "cannot",
            "can't",
            "unable to",
            "insufficient evidence",
            "no information",
            "not provided",
            "does not contain",
            "do not contain",
            "cannot identify",
            "cannot determine",
            "cannot complete",
            "cannot fulfill",
            "not available",
            "no narrative",
        )
    )


def _correct_abstention_denial(
    text: str,
    *,
    query: str,
    evidence: list[EvidenceChunk],
    filing_set: list[FilingRef],
    state: AgentState | None = None,
) -> str:
    """When evidence is present, replace LLM refusals with grounded excerpt synthesis."""
    if not evidence or not text.strip() or not _looks_like_refusal(text):
        return text
    q = query.lower()
    html = [c for c in evidence if "HTML" in str(getattr(c.source_type, "value", c.source_type))]
    if _is_comparison_query(query) and len(filing_set) >= 2 and html:
        by_acc: dict[str, list[EvidenceChunk]] = {}
        for chunk in html:
            acc = chunk.accession or ""
            if not acc and chunk.chunk_node_id.startswith("doc-"):
                acc = chunk.chunk_node_id.split("-")[1]
            by_acc.setdefault(acc or "unknown", []).append(chunk)
        if len(by_acc) >= 2:
            body_lines: list[str] = []
            for filing in filing_set:
                chunks = rank_evidence_by_topic(
                    by_acc.get(filing.accession) or [], query, max_chunks=3
                )
                if not chunks:
                    continue
                sents = _extract_risk_sentences(chunks[0].excerpt, query)
                lead = " ".join(sents) if sents else chunks[0].excerpt[:500].strip()
                body_lines.append(f"- {filing.form_type} ({filing.accession}): {lead}...")
            if len(body_lines) >= 2:
                topic = _risk_topic_phrase(query)
                intro = (
                    f"Both bound filings discuss risks related to {topic} "
                    "in Item 1A. Risk Factors."
                )
                return intro + "\n\n" + "\n".join(body_lines)
    if any(k in q for k in ("divest", "sale", "sold", "disposal", "md&a", "management")) and html:
        mda = rank_evidence_by_topic(html, query, max_chunks=5)
        lead = mda[0] if mda else max(html, key=lambda c: len(c.excerpt))
        return (
            "Based on the bound filing MD&A / narrative excerpt: "
            f"{lead.excerpt[:900].strip()}..."
        )
    if html:
        ranked = rank_evidence_by_topic(html, query, max_chunks=1)
        lead = ranked[0] if ranked else max(html, key=lambda c: len(c.excerpt))
        return (
            "Based on the bound filing narrative (HTML excerpt): "
            f"{lead.excerpt[:900].strip()}..."
        )
    template = _synthesize_template(
        evidence,
        query,
        filing_set,
        state=state,
    )
    answer = template.get("answer")
    if answer and answer.text and not _looks_like_refusal(answer.text):
        return answer.text
    return text


def _correct_revenue_denial(
    text: str,
    *,
    query: str,
    evidence: list[EvidenceChunk],
    filing_set: list[FilingRef],
    temporal_anchor: str,
    period_ends: str,
    state: AgentState | None = None,
) -> str:
    """When XBRL revenue for the bound period is in evidence, do not accept LLM refusals."""
    if not _is_revenue_metric_query(query):
        return text
    yoy_text = _synthesize_yoy_net_sales(evidence, filing_set, query, state=state)
    if yoy_text and _is_yoy_revenue_query(query, state, filing_set):
        lower = text.lower()
        if any(
            p in lower
            for p in (
                "not reported",
                "not available",
                "no revenue",
                "cannot",
                "unable",
                "insufficient",
            )
        ):
            return yoy_text
    lower = text.lower()
    refusal_phrases = (
        "not reported",
        "not available",
        "no revenue",
        "does not report",
        "do not report",
        "only contains data for the current quarter",
        "cannot determine",
    )
    if not any(p in lower for p in refusal_phrases):
        return text
    revenue_line = _best_revenue_excerpt(evidence, filing_set)
    if not revenue_line:
        return text
    anchor_note = ""
    if _normalize_anchor(temporal_anchor) in ("prior_quarter", "previous_quarter"):
        anchor_note = " (prior fiscal quarter relative to the latest 10-Q in the corpus)"
    return (
        f"Revenue for the bound reporting period (period end {period_ends}){anchor_note} "
        f"was {revenue_line}, per XBRL RevenueFromContractWithCustomerExcludingAssessedTax "
        f"in the selected filing."
    )


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


_THINK_OPEN = "<" + "think" + ">"
_THINK_CLOSE = "<" + "/" + "think" + ">"


def _strip_model_thinking(text: str) -> str:
    while _THINK_OPEN in text:
        start = text.index(_THINK_OPEN)
        end = text.find(_THINK_CLOSE, start)
        if end < 0:
            return text[:start].strip()
        text = text[:start] + text[end + len(_THINK_CLOSE) :]
    return text.strip()


def _message_content_to_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return _strip_model_thinking(content)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") in ("text", "output_text"):
                    parts.append(str(block.get("text", "")))
                else:
                    for key in ("text", "content", "output"):
                        if block.get(key):
                            parts.append(str(block[key]))
                            break
        return _strip_model_thinking("\n".join(p for p in parts if p))
    return _strip_model_thinking(str(content))


def _response_text(resp: object) -> str:
    """Normalize LangChain / LM Studio chat responses to plain answer text."""
    if resp is None:
        return ""
    text_attr = getattr(resp, "text", None)
    if isinstance(text_attr, str) and text_attr.strip():
        return _strip_model_thinking(text_attr)
    text = _message_content_to_text(getattr(resp, "content", None))
    if text.strip():
        return text
    extra = getattr(resp, "additional_kwargs", None) or {}
    if isinstance(extra, dict):
        for key in ("content", "reasoning_content", "refusal"):
            val = extra.get(key)
            if isinstance(val, str) and val.strip():
                return _strip_model_thinking(val)
    return ""


def _is_revenue_metric_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in ("revenue", "net sales", "total sales", "sales"))


def _is_yoy_revenue_query(
    query: str,
    state: AgentState | None,
    filing_set: list[FilingRef],
) -> bool:
    if not _is_revenue_metric_query(query):
        return False
    if not _yoy_comparison_intent(query, state):
        return False
    if len(filing_set) >= 2:
        return True
    return len(filing_set) == 1 and filing_set[0].form_type == "10-K"


def _parse_billions_from_excerpt(excerpt: str) -> float | None:
    m = re.search(r"\$([\d,.]+)\s+billion", excerpt, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _revenue_rows_for_filing(
    evidence: list[EvidenceChunk],
    filing: FilingRef,
    *,
    fy_end: int,
    intra_filing: bool = False,
) -> list[tuple[str, float, FilingRef]]:
    doc_id = f"doc-{filing.accession}"
    anchors = [filing.period_end]
    by_period: dict[date, tuple[str, float, FilingRef]] = {}
    for chunk in evidence:
        if not chunk.chunk_node_id.startswith(doc_id):
            continue
        if "RevenueFromContract" not in chunk.excerpt:
            continue
        if not intra_filing and not period_matches_anchor(
            None, anchors, excerpt=chunk.excerpt
        ):
            continue
        val = _parse_billions_from_excerpt(chunk.excerpt)
        if val is None:
            continue
        period_end = parse_period_end_from_excerpt(chunk.excerpt) or filing.period_end
        existing = by_period.get(period_end)
        if existing is None or val > existing[1]:
            label = FiscalPeriodLabel.from_filing(
                filing, fiscal_year_end_month=fy_end
            ).label
            if period_end != filing.period_end:
                label = f"FY ending {period_end}"
            by_period[period_end] = (label, val, filing)
    return [row for _, row in sorted(by_period.items(), key=lambda item: item[0], reverse=True)]


def _revenue_chunk_for_filing(
    evidence: list[EvidenceChunk],
    filing: FilingRef,
) -> EvidenceChunk | None:
    doc_id = f"doc-{filing.accession}"
    anchors = [filing.period_end]
    candidates: list[EvidenceChunk] = []
    for chunk in evidence:
        if not chunk.chunk_node_id.startswith(doc_id):
            continue
        if "RevenueFromContract" not in chunk.excerpt:
            continue
        if not period_matches_anchor(None, anchors, excerpt=chunk.excerpt):
            continue
        candidates.append(chunk)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda c: _parse_billions_from_excerpt(c.excerpt) or 0.0,
    )


def _synthesize_yoy_net_sales(
    evidence: list[EvidenceChunk],
    filing_set: list[FilingRef],
    query: str,
    *,
    state: AgentState | None = None,
) -> str | None:
    """Deterministic YoY net sales answer from per-filing RevenueFromContract facts."""
    if not _is_yoy_revenue_query(query, state, filing_set):
        return None
    ordered = sorted(filing_set, key=lambda f: f.period_end, reverse=True)
    fy_end = infer_fiscal_year_end_month(filing_set)
    rows: list[tuple[str, float, FilingRef]] = []
    if len(ordered) == 1 and ordered[0].form_type == "10-K":
        rows = _revenue_rows_for_filing(
            evidence, ordered[0], fy_end=fy_end, intra_filing=True
        )
    else:
        for filing in ordered:
            chunk = _revenue_chunk_for_filing(evidence, filing)
            if chunk is None:
                continue
            val = _parse_billions_from_excerpt(chunk.excerpt)
            if val is None:
                continue
            label = FiscalPeriodLabel.from_filing(filing, fiscal_year_end_month=fy_end).label
            rows.append((label, val, filing))
    if len(rows) < 2:
        return None
    label_new, val_new, _ = rows[0]
    label_old, val_old, _ = rows[1]
    delta = val_new - val_old
    pct = (delta / val_old) * 100.0 if val_old else 0.0
    if delta > 0:
        direction = "increased"
    elif delta < 0:
        direction = "decreased"
    else:
        direction = "was unchanged"
    return (
        f"Total net sales {direction} year over year, from ${val_old:.2f} billion in {label_old} "
        f"to ${val_new:.2f} billion in {label_new} "
        f"({delta:+.2f} billion, {pct:+.1f}%), per "
        f"RevenueFromContractWithCustomerExcludingAssessedTax in the bound 10-K filings."
    )


def _extract_numbers_from_evidence(evidence: list[EvidenceChunk]) -> list[str]:
    numbers: list[str] = []
    for chunk in evidence:
        numbers.extend(re.findall(r"\$?[\d,]+\.?\d*", chunk.excerpt))
    return numbers
