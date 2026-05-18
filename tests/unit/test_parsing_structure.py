
from parsing.docling_pipeline import parse_filing_path
from parsing.edgar_fetch import parse_filing_metadata_from_path


def test_table_headers_preserved(fixtures_dir):
    html_path = fixtures_dir / "sample_10k.html"
    filing = parse_filing_metadata_from_path(html_path, "0000320193", "10-K")
    doc = parse_filing_path(html_path, filing, use_docling=False)
    assert doc.tables, "expected at least one table"
    headers = doc.tables[0].headers
    assert any("2024" in str(cell) for row in headers for cell in row)
