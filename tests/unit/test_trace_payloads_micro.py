from models.enums import EvidenceSourceType, IntentSource, QueryIntent, SourceBias
from models.query import EvidenceChunk, IntentRouterTrace
from retrieval.orchestration.trace_payloads import build_micro_extractor_trace_payload


def test_micro_payload_shape() -> None:
    state = {
        "intent_trace": IntentRouterTrace(
            query_intent=QueryIntent.QUALITATIVE,
            intent_source=IntentSource.LLM,
            source_bias_applied=SourceBias.HTML_PRIMARY,
        ),
        "evidence_chunks": [
            EvidenceChunk(
                chunk_node_id="n1",
                excerpt="risk factor text",
                content_hash="h",
                source_type=EvidenceSourceType.HTML,
                section_id="html-risk",
            )
        ],
        "micro_ranked_count": 12,
        "micro_rank_trace": [
            {
                "chunk_node_id": "n1",
                "source_type": "HTML",
                "section_id": "html-risk",
                "score": 18.5,
                "components": {"relevance": 2.5, "qualitative_boost": 10.0},
                "excerpt_preview": "risk factor text",
            }
        ],
    }
    built = build_micro_extractor_trace_payload(state)
    assert built["payload"]["count_before"] == 12
    assert built["payload"]["count_after"] == 1
    assert built["payload"]["source_bias"] == "html_primary"
    assert len(built["payload"]["ranked"]) == 1
    assert built["payload"]["ranked"][0]["score"] is not None or "components" in built["payload"]["ranked"][0]
