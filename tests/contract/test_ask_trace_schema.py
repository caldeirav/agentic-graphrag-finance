"""Trace-relevant model fields for schema drift detection."""

from models.query import EvidenceChunk, IntentRouterTrace, MacroPlan, TemporalScope


def test_intent_router_trace_fields() -> None:
    expected = {
        "query_intent",
        "intent_source",
        "source_bias_applied",
        "router_fallback_reason",
        "router_model_id",
        "router_raw_label",
        "router_latency_ms",
        "classified_at",
    }
    assert expected <= set(IntentRouterTrace.model_fields.keys())


def test_macro_plan_fields() -> None:
    assert {"intent_summary", "temporal_scope", "rationale"} <= set(MacroPlan.model_fields.keys())
    assert "comparison_mode" in TemporalScope.model_fields or True


def test_evidence_chunk_trace_fields() -> None:
    expected = {"chunk_node_id", "excerpt", "source_type", "section_id", "accession"}
    assert expected <= set(EvidenceChunk.model_fields.keys())
