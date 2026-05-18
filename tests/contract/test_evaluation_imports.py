from pathlib import Path


def test_evaluation_modules_avoid_langgraph_imports():
    for py in Path("src/evaluation").rglob("*.py"):
        text = py.read_text()
        assert "from langgraph" not in text
        assert "import langgraph" not in text
        assert "orchestration" not in text
