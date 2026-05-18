from graph.builder import build_snapshot
from models.enums import GraphNodeType


def test_numeric_value_traceable_in_graph(sample_parsed_document):
    snap = build_snapshot("0000320193", [sample_parsed_document])
    row_nodes = [n for n in snap.nodes if n.node_type == GraphNodeType.CHUNK_ROW]
    excerpts = " ".join(n.source_ref for n in row_nodes)
    assert "352,583" in excerpts or "352" in excerpts
