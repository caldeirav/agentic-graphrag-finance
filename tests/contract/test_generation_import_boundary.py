"""Static import boundary for evaluation/generation (011)."""

import ast
from pathlib import Path

FORBIDDEN = (
    "retrieval",
    "ingestion",
    "cli",
    "graph",
)
GENERATION_ROOT = Path("src/evaluation/generation")


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_generation_modules_no_forbidden_imports():
    violations: list[str] = []
    for path in sorted(GENERATION_ROOT.rglob("*.py")):
        imports = _imports_in_file(path)
        hit = imports & set(FORBIDDEN)
        if hit:
            violations.append(f"{path}: {sorted(hit)}")
    assert not violations, violations
