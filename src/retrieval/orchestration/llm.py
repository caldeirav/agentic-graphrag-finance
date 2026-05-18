"""LM Studio / Qwen LLM factory."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from langchain_openai import ChatOpenAI

_DEFAULT_BASE_URL = "http://localhost:1234/v1"
_DEFAULT_MODEL = "qwen/qwen3.6-35b-a3b"


def _strip_placeholder(value: str, fallback: str) -> str:
    """Ignore bash-style ${VAR:-default} literals left in YAML."""
    if value.startswith("${"):
        return fallback
    return value


def load_lm_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/lm_studio.yaml")
    cfg: dict = {}
    if path.exists():
        cfg = yaml.safe_load(path.read_text()) or {}

    base = os.environ.get("LM_STUDIO_BASE_URL") or cfg.get("base_url", _DEFAULT_BASE_URL)
    model = os.environ.get("LM_STUDIO_MODEL") or cfg.get("model", _DEFAULT_MODEL)
    return {
        "base_url": _strip_placeholder(str(base), _DEFAULT_BASE_URL),
        "model": _strip_placeholder(str(model), _DEFAULT_MODEL),
        "temperature": float(cfg.get("temperature", 0.1)),
        "max_tokens": int(cfg.get("max_tokens", 4096)),
    }


def create_chat_llm(*, mock: bool = False) -> ChatOpenAI:
    if mock or os.environ.get("USE_MOCK_LLM", "0") == "1":
        return ChatOpenAI(
            model="mock",
            base_url="http://localhost:9999/v1",
            api_key="mock",
            temperature=0,
            max_tokens=256,
        )
    cfg = load_lm_config()
    return ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
