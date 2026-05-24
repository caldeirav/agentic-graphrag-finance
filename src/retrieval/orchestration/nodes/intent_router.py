"""LLM intent router: numeric / qualitative / hybrid with keyword fallback."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from models.enums import (
    IntentSource,
    QueryIntent,
    RouterFallbackReason,
    SourceBias,
)
from models.query import IntentRouterTrace
from retrieval.orchestration.llm import create_chat_llm
from retrieval.orchestration.nodes.macro_router import _extract_json_from_llm
from retrieval.orchestration.state import AgentState
from tracing.console_trace.llm import traced_llm_invoke

_INTENT_TO_BIAS = {
    QueryIntent.NUMERIC: SourceBias.XBRL_PRIMARY,
    QueryIntent.QUALITATIVE: SourceBias.HTML_PRIMARY,
    QueryIntent.HYBRID: SourceBias.BLENDED,
}


def load_intent_router_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/intent_router.yaml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def classify_intent_keywords(query: str, cfg: dict | None = None) -> QueryIntent:
    cfg = cfg or load_intent_router_config()
    fb = cfg.get("keyword_fallback", {})
    q = query.lower()
    hybrid_hits = sum(1 for w in fb.get("hybrid", []) if w in q)
    qual_hits = sum(1 for w in fb.get("qualitative", []) if w in q)
    num_hits = sum(1 for w in fb.get("numeric", []) if w in q)
    if hybrid_hits >= 2 or (num_hits >= 1 and qual_hits >= 1):
        return QueryIntent.HYBRID
    if qual_hits > num_hits:
        return QueryIntent.QUALITATIVE
    if num_hits > 0:
        return QueryIntent.NUMERIC
    return QueryIntent.QUALITATIVE


def _parse_intent_label(raw: object) -> QueryIntent | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    for intent in QueryIntent:
        if intent.value == text:
            return intent
    return None


def _intent_from_llm(query: str, cfg: dict) -> tuple[QueryIntent | None, str, str, dict]:
    llm = create_chat_llm()
    prompt = cfg.get("prompt", "").strip() or (
        'Return JSON: {"query_intent": "numeric"|"qualitative"|"hybrid"}'
    )
    messages = [
        SystemMessage(content="You classify financial disclosure query intent."),
        HumanMessage(content=f"{prompt}\n\nQuestion: {query}"),
    ]
    resp, trace_patch = traced_llm_invoke("intent_router", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    data = _extract_json_from_llm(text)
    intent = _parse_intent_label(data.get("query_intent"))
    model_id = getattr(llm, "model_name", None) or getattr(llm, "model", "") or "local-llm"
    return intent, text[:500], str(model_id), trace_patch


def intent_router(state: AgentState) -> dict:
    query = state.get("query", "")
    cfg = load_intent_router_config()
    started = time.perf_counter()

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        intent = classify_intent_keywords(query, cfg)
        trace = IntentRouterTrace(
            query_intent=intent,
            intent_source=IntentSource.KEYWORD_FALLBACK,
            source_bias_applied=_INTENT_TO_BIAS[intent],
            router_fallback_reason=RouterFallbackReason.MOCK_LLM,
            router_latency_ms=int((time.perf_counter() - started) * 1000),
            classified_at=datetime.now(UTC),
        )
        return {
            "intent_trace": trace,
            "graph_traversal": [{"node_id": "intent_router", "stage": "intent_router"}],
        }

    intent: QueryIntent | None = None
    raw_label = ""
    model_id = ""
    trace_patch: dict = {}
    fallback_reason: RouterFallbackReason | None = None
    source = IntentSource.LLM

    try:
        intent, raw_label, model_id, trace_patch = _intent_from_llm(query, cfg)
    except Exception:
        fallback_reason = RouterFallbackReason.ROUTER_ERROR
        source = IntentSource.KEYWORD_FALLBACK

    if intent is None:
        intent = classify_intent_keywords(query, cfg)
        source = IntentSource.KEYWORD_FALLBACK
        fallback_reason = fallback_reason or RouterFallbackReason.INVALID_LABEL

    trace = IntentRouterTrace(
        query_intent=intent,
        intent_source=source,
        source_bias_applied=_INTENT_TO_BIAS[intent],
        router_fallback_reason=fallback_reason,
        router_model_id=model_id if source == IntentSource.LLM else "",
        router_raw_label=raw_label,
        router_latency_ms=int((time.perf_counter() - started) * 1000),
        classified_at=datetime.now(UTC),
    )
    out: dict = {
        "intent_trace": trace,
        "graph_traversal": [{"node_id": "intent_router", "stage": "intent_router"}],
    }
    if trace_patch.get("trace_events"):
        out["trace_events"] = trace_patch["trace_events"]
    return out
