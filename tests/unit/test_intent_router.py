
from models.enums import IntentSource, QueryIntent, RouterFallbackReason
from retrieval.orchestration.nodes.intent_router import classify_intent_keywords, intent_router


def test_keyword_fallback_numeric() -> None:
    intent = classify_intent_keywords("What was total revenue in Q4?")
    assert intent == QueryIntent.NUMERIC


def test_keyword_fallback_qualitative() -> None:
    intent = classify_intent_keywords("What are the principal risk factors in the 10-K?")
    assert intent == QueryIntent.QUALITATIVE


def test_intent_router_mock_llm(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    out = intent_router({"query": "Describe MD&A liquidity risks"})
    trace = out["intent_trace"]
    assert trace.intent_source == IntentSource.KEYWORD_FALLBACK
    assert trace.router_fallback_reason == RouterFallbackReason.MOCK_LLM
    assert trace.query_intent in (QueryIntent.QUALITATIVE, QueryIntent.HYBRID, QueryIntent.NUMERIC)
