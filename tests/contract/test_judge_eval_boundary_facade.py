import ast
from pathlib import Path


def test_retrieval_service_imports_only_ask_judge_facade():
    path = Path("src/retrieval/service.py")
    tree = ast.parse(path.read_text())
    eval_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("evaluation"):
            eval_imports.append(node.module)
    assert "evaluation.ask_judge" in eval_imports
    assert not any(m.startswith("evaluation.validator") for m in eval_imports)
