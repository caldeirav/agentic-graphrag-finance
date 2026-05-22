from models.enums import IntentSource, QueryIntent, RouterFallbackReason, SourceBias
from models.query import IntentRouterTrace, TrajectoryRecord
from tracing.mlflow_langgraph import build_trajectory_from_state


def test_trajectory_includes_intent_router() -> None:
    trace = IntentRouterTrace(
        query_intent=QueryIntent.NUMERIC,
        intent_source=IntentSource.LLM,
        source_bias_applied=SourceBias.XBRL_PRIMARY,
        router_model_id="test-model",
    )
    traj = build_trajectory_from_state({"intent_trace": trace, "graph_traversal": []})
    assert traj.intent_router is not None
    assert traj.intent_router.query_intent == QueryIntent.NUMERIC


def test_fallback_trace_has_reason() -> None:
    trace = IntentRouterTrace(
        query_intent=QueryIntent.QUALITATIVE,
        intent_source=IntentSource.KEYWORD_FALLBACK,
        source_bias_applied=SourceBias.HTML_PRIMARY,
        router_fallback_reason=RouterFallbackReason.MOCK_LLM,
    )
    assert trace.router_fallback_reason == RouterFallbackReason.MOCK_LLM
    assert trace.intent_source != IntentSource.LLM
