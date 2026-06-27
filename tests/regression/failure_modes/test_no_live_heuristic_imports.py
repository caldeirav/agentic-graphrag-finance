"""Regression: live synthesis must not import retired heuristic routers (023 US6)."""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SYNTHESIS = _REPO / "src/retrieval/synthesis.py"

_FORBIDDEN_LIVE_IMPORTS = (
    "point_fact_selection",
    "html_table_fallback",
    "ratio_pair_resolution",
)


def test_synthesis_live_path_has_no_retired_heuristic_imports() -> None:
    tree = ast.parse(_SYNTHESIS.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(node.module.split(".")[-1])
                imported.add(alias.name)
    for name in _FORBIDDEN_LIVE_IMPORTS:
        assert name not in imported, f"synthesis.py must not import {name} in live path"
