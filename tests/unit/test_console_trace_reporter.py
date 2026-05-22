from models.enums import IntentSource, QueryIntent, RouterFallbackReason, SourceBias
from models.query import IntentRouterTrace
from tracing.console_trace.emitter import trace_stage_end
from tracing.console_trace.models import TraceLevel, TraceRunConfig
from tracing.console_trace.reporter import ConsoleTraceReporter, strip_ansi


def _intent_state() -> dict:
    trace = IntentRouterTrace(
        query_intent=QueryIntent.QUALITATIVE,
        intent_source=IntentSource.KEYWORD_FALLBACK,
        source_bias_applied=SourceBias.HTML_PRIMARY,
        router_fallback_reason=RouterFallbackReason.MOCK_LLM,
    )
    end = trace_stage_end(
        "intent_router",
        duration_ms=12,
        decision_summary="intent=qualitative source=keyword_fallback",
        payload={
            "query_intent": "qualitative",
            "intent_source": "keyword_fallback",
            "router_fallback_reason": "mock_llm",
        },
    )
    return {
        "intent_trace": trace,
        "trace_events": end["trace_events"],
    }


def test_render_normalized_plain_text() -> None:
    reporter = ConsoleTraceReporter(
        TraceRunConfig(level=TraceLevel.NORMAL, use_color=False, panel_enabled=False)
    )
    text = reporter.render_all_normalized(_intent_state())
    assert "Intent router" in text or "intent_router" in text
    assert "keyword_fallback" in text
    assert strip_ansi(text) == text


def test_verbose_includes_llm_io_lines() -> None:
    from tracing.console_trace.models import LlmIoRecord, TraceEvent, TraceEventType

    reporter = ConsoleTraceReporter(TraceRunConfig(level=TraceLevel.VERBOSE, use_color=False))
    state = _intent_state()
    state["trace_events"].append(
        TraceEvent(
            stage_id="intent_router",
            event_type=TraceEventType.LLM_IO,
            llm_io=LlmIoRecord(
                model_id="mock",
                messages_preview=[{"role": "human", "content": "question"}],
                response_preview='{"query_intent":"qualitative"}',
            ),
        )
    )
    text = reporter.render_all_normalized(state)
    assert "llm:" in text or "mock" in text
