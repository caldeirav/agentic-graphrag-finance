"""Ingestion layer must not import graph, retrieval, or evaluation."""

import ast
from pathlib import Path


def _imports_in_package(pkg: str) -> set[str]:
    root = Path("src") / pkg
    found: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_ingestion_import_boundary():
    forbidden = {"graph", "retrieval", "evaluation"}
    imports = _imports_in_package("ingestion")
    assert not imports & forbidden, f"ingestion imports forbidden layers: {imports & forbidden}"
