from models.enums import ComparisonMode
from retrieval.orchestration.nodes.macro_router import (
    _extract_json_from_llm,
    _parse_comparison_mode,
)


def test_parse_comparison_mode_null():
    assert _parse_comparison_mode(None) == ComparisonMode.YOY


def test_parse_comparison_mode_variants():
    assert _parse_comparison_mode("QoQ") == ComparisonMode.QOQ
    assert _parse_comparison_mode("sequential") == ComparisonMode.SEQUENTIAL


def test_extract_json_from_markdown_fence():
    text = '```json\n{"comparison_mode": null, "intent_summary": "revenue"}\n```'
    data = _extract_json_from_llm(text)
    assert data["intent_summary"] == "revenue"
    assert _parse_comparison_mode(data.get("comparison_mode")) == ComparisonMode.YOY
