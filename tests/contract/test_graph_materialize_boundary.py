"""Graph materialization must not import ingestion, retrieval, or evaluation."""

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


def test_graph_builder_import_boundary():
    forbidden = {"ingestion", "retrieval", "evaluation"}
    for rel in ("src/graph/builder.py", "src/graph/docling_graph_mapper.py"):
        imports = _imports_in_module(Path(rel))
        assert not imports & forbidden, f"{rel} imports forbidden layers: {imports & forbidden}"
