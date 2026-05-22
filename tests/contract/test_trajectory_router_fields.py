from models.enums import IntentSource, QueryIntent, SourceBias
from models.query import IntentRouterTrace, TrajectoryRecord


def test_trajectory_json_schema_has_intent_router() -> None:
    trace = IntentRouterTrace(
        query_intent=QueryIntent.HYBRID,
        intent_source=IntentSource.LLM,
        source_bias_applied=SourceBias.BLENDED,
        router_model_id="m1",
    )
    record = TrajectoryRecord(intent_router=trace)
    data = record.model_dump(mode="json")
    assert "intent_router" in data
    assert data["intent_router"]["query_intent"] == "hybrid"
    assert data["intent_router"]["intent_source"] == "llm"
    assert data["intent_router"]["source_bias_applied"] == "blended"
