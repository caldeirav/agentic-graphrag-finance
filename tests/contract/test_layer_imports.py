"""Layer import boundary checks."""

import ast
from pathlib import Path


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def test_evaluation_does_not_import_orchestration():
    eval_dir = Path("src/evaluation")
    allowed_retrieval = {"runner.py", "cli.py"}
    for py in eval_dir.rglob("*.py"):
        if py.name == "__init__.py":
            continue
        imports = _imports_in_file(py)
        if "retrieval" in imports:
            assert py.name in allowed_retrieval
        assert "orchestration" not in py.read_text()


def test_parsing_does_not_import_graph():
    for py in Path("src/parsing").rglob("*.py"):
        imports = _imports_in_file(py)
        assert "graph" not in imports
        assert "retrieval" not in imports
