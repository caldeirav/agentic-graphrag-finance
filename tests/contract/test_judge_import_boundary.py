import ast
from pathlib import Path

FORBIDDEN = ("retrieval", "ingestion", "graph")
JUDGE_MODULES = (
    Path("src/evaluation/validator"),
    Path("src/evaluation/judges"),
    Path("src/evaluation/ask_judge.py"),
)


def test_judge_modules_no_forbidden_imports():
    violations: list[str] = []
    paths = []
    for base in JUDGE_MODULES:
        if base.is_file():
            paths.append(base)
        else:
            paths.extend(base.rglob("*.py"))
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
