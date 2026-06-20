"""Contract test: review package must not import retrieval or ingestion (018)."""

import ast
from pathlib import Path

FORBIDDEN = ("retrieval", "ingestion", "graph")
REVIEW_ROOT = Path("src/evaluation/generation/review")


def test_review_modules_no_forbidden_imports():
    violations: list[str] = []
    paths = list(REVIEW_ROOT.rglob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in FORBIDDEN:
                        violations.append(f"{path}:{top}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in FORBIDDEN:
                    violations.append(f"{path}:{top}")
    assert not violations, violations
