"""Unit tests for live-eval guards on paper releases (012)."""

import pytest

from evaluation.reproduction.runner import _require_live_eval


def test_paper_live_smoke_rejects_mock_judge(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "0")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with pytest.raises(RuntimeError, match="live Gemini judge"):
        _require_live_eval("paper-live-smoke")


def test_paper_v1_rejects_mock_llm(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_JUDGE", "0")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with pytest.raises(RuntimeError, match="live agent LLM"):
        _require_live_eval("paper-v1.0")


def test_paper_smoke_allows_mock(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    _require_live_eval("paper-smoke")
