
from graph.builder import build_snapshot
from graph.store import load_snapshot, save_snapshot
from parsing.docling_pipeline import parse_filing_path
from parsing.edgar_fetch import parse_filing_metadata_from_path
from parsing.validators import validate_parsed_document


def test_ingest_build_roundtrip(tmp_path, fixtures_dir):
    html = fixtures_dir / "sample_10k.html"
    filing = parse_filing_metadata_from_path(html, "0000320193", "10-K")
    doc = parse_filing_path(html, filing, use_docling=False)
    validate_parsed_document(doc)
    snap = build_snapshot("0000320193", [doc], snapshot_id="integration-001")
    save_snapshot(snap, tmp_path)
    loaded = load_snapshot("0000320193", "integration-001", tmp_path)
    assert len(loaded.nodes) == len(snap.nodes)
