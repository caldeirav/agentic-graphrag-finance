from retrieval.orchestration.meso_scoring import score_section, section_trace_row
from retrieval.orchestration.trace_payloads import build_meso_router_trace_payload


def test_meso_score_section_xbrl_boost() -> None:
    score, components = score_section(
        label="XBRL financial facts",
        node_id="doc-0000320193-26-000006-xbrl-facts",
        section_id="",
        query="revenue for that quarter",
        prefer_html=False,
        filing_accessions=["0000320193-26-000006"],
    )
    assert score >= 2.0
    assert components.get("xbrl_numeric_query") == 2.0


def test_meso_trace_payload_includes_labels_and_components() -> None:
    row = section_trace_row(
        section_node_id="doc-xbrl-facts",
        label="XBRL facts",
        section_id="",
        score=3.2,
        components={"xbrl_numeric_query": 2.0, "total": 3.2},
        path=["doc-xbrl-facts"],
    )
    state = {
        "section_candidates": [],
        "meso_section_trace": [row],
    }
    built = build_meso_router_trace_payload(state)
    assert built["payload"]["top_sections"][0]["label"] == "XBRL facts"
    assert built["payload"]["top_sections"][0]["components"]["xbrl_numeric_query"] == 2.0
