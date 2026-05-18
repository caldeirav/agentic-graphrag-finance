import ast
from pathlib import Path


def test_cli_does_not_import_orchestration():
    root = Path("src/cli")
    forbidden = "retrieval.orchestration"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), path
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), path
