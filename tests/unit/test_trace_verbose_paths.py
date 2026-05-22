from models.enums import EvidenceSourceType
from models.query import EvidenceChunk
from tracing.console_trace.models import TraceEvent, TraceEventType, TraceLevel, TraceRunConfig
from tracing.console_trace.registry import ASK_TRACE_REGISTRY


def test_micro_verbose_renders_structural_paths() -> None:
    renderer = ASK_TRACE_REGISTRY["micro_extractor"].renderer
    state = {
        "evidence_chunks": [
            EvidenceChunk(
                chunk_node_id="doc-1-xbrl-abc",
                excerpt="XBRL Revenue: $1",
                content_hash="h",
                source_type=EvidenceSourceType.XBRL,
            )
        ],
        "graph_traversal": [
            {
                "node_id": "doc-1-xbrl-abc",
                "stage": "micro",
                "path_edge_types": ["CONTAINS", "CONTAINS"],
                "path_node_ids": ["doc-1", "sec-1", "doc-1-xbrl-abc"],
            }
        ],
        "trace_events": [
            TraceEvent(
                stage_id="micro_extractor",
                event_type=TraceEventType.STAGE_END,
                decision_summary="evidence 5→1",
                payload={
                    "count_before": 5,
                    "count_after": 1,
                    "source_bias": "xbrl_primary",
                    "ranked": [
                        {
                            "chunk_node_id": "doc-1-xbrl-abc",
                            "score": 12.5,
                            "source_type": "XBRL",
                            "components": {"relevance": 5.0},
                            "excerpt_preview": "XBRL Revenue",
                        }
                    ],
                },
            )
        ],
    }
    lines = renderer(
        "micro_extractor",
        state,
        state["trace_events"],
        TraceRunConfig(level=TraceLevel.VERBOSE, use_color=False),
    )
    text = "\n".join(lines)
    assert "path doc-1-xbrl-abc" in text
    assert "CONTAINS" in text
