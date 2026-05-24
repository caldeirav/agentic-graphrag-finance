"""Unit tests for LLM factory."""

from __future__ import annotations

from retrieval.orchestration.llm import create_chat_llm


def test_create_chat_llm_accepts_temperature_override(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "0")
    llm = create_chat_llm(temperature=0)
    assert llm.temperature == 0
