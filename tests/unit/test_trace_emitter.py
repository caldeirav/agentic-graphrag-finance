from tracing.console_trace.emitter import trace_stage_end, trace_stage_start
from tracing.console_trace.models import TraceEvent, TraceEventType


def test_trace_stage_start_event() -> None:
    patch = trace_stage_start("intent_router")
    events = patch["trace_events"]
    assert len(events) == 1
    assert events[0].stage_id == "intent_router"
    assert events[0].event_type == TraceEventType.STAGE_START


def test_trace_stage_end_event() -> None:
    patch = trace_stage_end(
        "micro_extractor",
        duration_ms=42,
        decision_summary="evidence 10→5",
        payload={"count_after": 5},
    )
    ev = patch["trace_events"][0]
    assert ev.duration_ms == 42
    assert ev.payload["count_after"] == 5


def test_merge_trace_events_type() -> None:
    from retrieval.orchestration.state import _merge_trace_events

    left = [TraceEvent(stage_id="a", event_type=TraceEventType.STAGE_START)]
    right = [{"stage_id": "b", "event_type": "stage_end"}]
    merged = _merge_trace_events(left, right)
    assert len(merged) == 2
    assert merged[1].stage_id == "b"
