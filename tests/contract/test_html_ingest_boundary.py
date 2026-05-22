import ast
from pathlib import Path


def test_html_narrative_module_has_no_upstream_layer_imports() -> None:
    path = Path("src/ingestion/html_narrative.py")
    tree = ast.parse(path.read_text())
    forbidden = {"parsing", "graph", "retrieval", "evaluation"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top not in forbidden, f"forbidden import {alias.name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            assert top not in forbidden, f"forbidden import from {node.module}"
