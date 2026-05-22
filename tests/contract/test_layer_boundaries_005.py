import ast
from pathlib import Path


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    tops: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        if isinstance(node, ast.ImportFrom) and node.module:
            tops.add(node.module.split(".")[0])
    return tops


def test_parsing_html_narrative_no_retrieval() -> None:
    tops = _imports_in(Path("src/parsing/html_narrative.py"))
    assert "retrieval" not in tops


def test_graph_mapper_no_html_ingest_network() -> None:
    tops = _imports_in(Path("src/graph/docling_graph_mapper.py"))
    assert "ingestion" not in tops
