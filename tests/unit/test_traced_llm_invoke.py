from langchain_core.messages import HumanMessage

from tracing.console_trace.context import set_trace_reporter
from tracing.console_trace.llm import traced_llm_invoke
from tracing.console_trace.models import TraceEventType, TraceLevel, TraceRunConfig
from tracing.console_trace.reporter import ConsoleTraceReporter


class _FakeLLM:
    model_name = "fake"
    temperature = 0.0
    max_tokens = 100

    def invoke(self, messages):
        return type("R", (), {"content": "ok"})()


def test_traced_llm_invoke_emits_event() -> None:
    set_trace_reporter(ConsoleTraceReporter(TraceRunConfig(level=TraceLevel.NORMAL)))
    _, patch = traced_llm_invoke("synthesize", _FakeLLM(), [HumanMessage(content="x" * 2000)])
    ev = patch["trace_events"][0]
    assert ev.event_type == TraceEventType.LLM_IO
    assert ev.llm_io is not None
    assert len(ev.llm_io.messages_preview[0]["content"]) <= 803
    set_trace_reporter(None)
