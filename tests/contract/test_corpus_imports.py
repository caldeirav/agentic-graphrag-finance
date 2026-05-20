"""Corpus orchestration must not import graph, retrieval, or evaluation."""

import ast
from pathlib import Path


def _imports_in_module(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_corpus_module_import_boundary():
    path = Path("src/ingestion/corpus.py")
    forbidden = {"graph", "retrieval", "evaluation"}
    imports = _imports_in_module(path)
    assert not imports & forbidden, f"corpus imports forbidden layers: {imports & forbidden}"
