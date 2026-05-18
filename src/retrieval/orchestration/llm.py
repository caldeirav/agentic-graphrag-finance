"""LM Studio / Qwen LLM factory."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from langchain_openai import ChatOpenAI


def load_lm_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/lm_studio.yaml")
    raw = path.read_text()
    for key, default in [
        ("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
        ("LM_STUDIO_MODEL", "qwen/qwen3.6-35b-a3b"),
    ]:
        raw = raw.replace(f"${{{key}:-", "${").replace("}", "}")
        raw = re.sub(rf"\$\{{{key}\}}", os.environ.get(key, default), raw)
    return yaml.safe_load(raw)


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
    base = os.environ.get("LM_STUDIO_BASE_URL", cfg.get("base_url", "http://localhost:1234/v1"))
    model = os.environ.get("LM_STUDIO_MODEL", cfg.get("model", "qwen/qwen3.6-35b-a3b"))
    return ChatOpenAI(
        model=model,
        base_url=base,
        api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
        temperature=float(cfg.get("temperature", 0.1)),
        max_tokens=int(cfg.get("max_tokens", 4096)),
    )
