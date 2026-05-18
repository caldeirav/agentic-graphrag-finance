from graph.builder import build_snapshot
from parsing.validators import validate_parsed_document


def test_parsed_document_maps_to_graph(sample_parsed_document):
    validate_parsed_document(sample_parsed_document)
    snap = build_snapshot("0000320193", [sample_parsed_document])
    assert len(snap.nodes) > 0
    assert any(n.node_type.value == "DOCUMENT" for n in snap.nodes)
    assert any(n.node_type.value == "CHUNK_TABLE" for n in snap.nodes)
