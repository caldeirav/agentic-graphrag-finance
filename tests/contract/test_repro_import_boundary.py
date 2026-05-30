"""Import boundary: reproduction modules must not import retrieval orchestration."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = ("retrieval.orchestration",)
MODULES = (
    "src/evaluation/reproduction/relevance.py",
    "src/evaluation/reproduction/flat_chunk.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_repro_modules_avoid_orchestration_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in MODULES:
        imports = _imports(root / rel)
        for forbidden in FORBIDDEN:
            assert not any(i == forbidden or i.startswith(f"{forbidden}.") for i in imports), (
                f"{rel} imports forbidden {forbidden}: {imports}"
            )
