"""Evaluation layer must not import macro planner (T042)."""

import ast
from pathlib import Path


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_evaluation_does_not_import_macro_planner():
    for py in Path("src/evaluation").rglob("*.py"):
        if py.name == "__init__.py":
            continue
        text = py.read_text()
        assert "retrieval.macro.planner" not in text
        assert "from retrieval.macro import plan_macro_binding" not in text
        for mod in _imports_from(py):
            assert mod != "retrieval.macro.planner"
