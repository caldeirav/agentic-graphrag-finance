from models.enums import (
    IntentSource,
    QueryIntent,
    RouterFallbackReason,
    SourceBias,
)


def test_router_trace_enum_values() -> None:
    assert QueryIntent.NUMERIC.value == "numeric"
    assert QueryIntent.QUALITATIVE.value == "qualitative"
    assert QueryIntent.HYBRID.value == "hybrid"
    assert IntentSource.LLM.value == "llm"
    assert IntentSource.KEYWORD_FALLBACK.value == "keyword_fallback"
    assert SourceBias.XBRL_PRIMARY.value == "xbrl_primary"
    assert SourceBias.HTML_PRIMARY.value == "html_primary"
    assert SourceBias.BLENDED.value == "blended"
    assert RouterFallbackReason.MOCK_LLM.value == "mock_llm"
