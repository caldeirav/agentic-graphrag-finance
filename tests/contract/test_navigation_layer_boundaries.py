"""Contract: evaluation layer must not import navigation planner (009)."""

from __future__ import annotations

import ast
from pathlib import Path


def test_evaluation_does_not_import_navigation_planner():
    root = Path("src/evaluation")
    forbidden = "retrieval.navigation.planner"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert forbidden not in (node.module or "")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert forbidden not in alias.name
