"""Bound LLM prompt size for local models (scaled to LM Studio n_ctx)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from models.enums import EvidenceSourceType, QueryIntent
from models.query import EvidenceChunk

_CHARS_PER_TOKEN = 3.2
_TEMPLATE_RESERVE_TOKENS = 900
_CONTEXT_SLACK_TOKENS = 384

_PROFILE_4K = {
    "context_tokens": 4096,
    "max_evidence_chunks": 5,
    "max_excerpt_chars": 500,
    "max_prompt_chars": 10_000,
    "max_completion_tokens": 1024,
}


def is_context_length_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "n_keep" in text
        and "n_ctx" in text
        or "context length" in text
        or "larger context length" in text
        or "shorter input" in text
    )


def _parse_n_ctx_from_error(exc: BaseException) -> int | None:
    match = re.search(r"n_ctx:\s*(\d+)", str(exc), re.I)
    return int(match.group(1)) if match else None


def derive_limits(context_tokens: int, max_completion_tokens: int) -> dict[str, int]:
    """Compute safe prompt/evidence caps from total context and completion reserve."""
    max_input_tokens = max(
        1024,
        context_tokens - max_completion_tokens - _CONTEXT_SLACK_TOKENS,
    )
    max_prompt_chars = int(max_input_tokens * _CHARS_PER_TOKEN)
    evidence_tokens = max(512, max_input_tokens - _TEMPLATE_RESERVE_TOKENS)
    evidence_chars = int(evidence_tokens * _CHARS_PER_TOKEN)
    max_chunks = min(12, max(3, evidence_chars // 600))
    max_excerpt = max(300, evidence_chars // max_chunks)
    return {
        "context_tokens": context_tokens,
        "max_evidence_chunks": max_chunks,
        "max_excerpt_chars": max_excerpt,
        "max_prompt_chars": max_prompt_chars,
        "max_completion_tokens": max_completion_tokens,
    }


def probe_lm_studio_context_tokens(
    base_url: str | None = None,
    model: str | None = None,
) -> int | None:
    """Read n_ctx from LM Studio /v1/models when available."""
    if os.environ.get("LLM_PROBE_CONTEXT", "1") == "0":
        return None
    try:
        import httpx
    except ImportError:
        return None

    url_base = (base_url or os.environ.get("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1").rstrip(
        "/"
    )
    model_id = model or os.environ.get("LM_STUDIO_MODEL", "")
    if not model_id:
        cfg_path = Path("configs/lm_studio.yaml")
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text()) or {}
            model_id = str(cfg.get("model", ""))

    try:
        resp = httpx.get(f"{url_base}/models", timeout=5.0)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None

    for entry in models:
        if not isinstance(entry, dict):
            continue
        mid = entry.get("id") or entry.get("model") or ""
        if model_id and mid != model_id:
            continue
        for key in (
            "max_context_length",
            "max_context_tokens",
            "context_length",
            "n_ctx",
        ):
            val = entry.get(key)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    continue
    return None


def _cap_limit(requested: int, safe: int) -> int:
    return min(requested, safe) if requested > 0 else safe


def load_context_budget(
    config_path: Path | None = None,
    *,
    context_tokens_override: int | None = None,
    profile_override: dict[str, int] | None = None,
) -> dict[str, int]:
    path = config_path or Path("configs/lm_studio.yaml")
    cfg: dict[str, Any] = {}
    if path.exists():
        cfg = yaml.safe_load(path.read_text()) or {}

    configured_ctx = int(
        os.environ.get("LLM_CONTEXT_TOKENS", cfg.get("context_tokens", 4096))
    )
    if context_tokens_override is not None:
        context_tokens = context_tokens_override
    else:
        probed = probe_lm_studio_context_tokens()
        if probed is not None and probed < configured_ctx:
            context_tokens = probed
        else:
            context_tokens = configured_ctx

    if profile_override is not None:
        return dict(profile_override)

    max_completion = int(
        os.environ.get(
            "LLM_MAX_COMPLETION_TOKENS",
            cfg.get("max_tokens", _PROFILE_4K["max_completion_tokens"]),
        )
    )
    safe = derive_limits(context_tokens, max_completion)

    def _requested(key: str, env_key: str) -> int | None:
        if env_key in os.environ:
            return int(os.environ[env_key])
        if key in cfg:
            return int(cfg[key])
        return None

    for key, env_key in (
        ("max_evidence_chunks", "LLM_MAX_EVIDENCE_CHUNKS"),
        ("max_excerpt_chars", "LLM_MAX_EXCERPT_CHARS"),
        ("max_prompt_chars", "LLM_MAX_PROMPT_CHARS"),
    ):
        req = _requested(key, env_key)
        if req is not None:
            safe[key] = _cap_limit(req, safe[key])

    safe["max_completion_tokens"] = max_completion
    return safe


def _is_html(chunk: EvidenceChunk) -> bool:
    st = getattr(chunk.source_type, "value", str(chunk.source_type))
    return st == EvidenceSourceType.HTML.value or st == EvidenceSourceType.HTML


def compact_evidence_for_llm(
    evidence: list[EvidenceChunk],
    *,
    query: str = "",
    query_intent: QueryIntent | None = None,
    budget: dict[str, int] | None = None,
) -> list[EvidenceChunk]:
    """Return evidence copies with truncated excerpts sized for the configured context."""
    if not evidence:
        return []

    limits = budget or load_context_budget()
    max_chunks = limits["max_evidence_chunks"]
    max_chars = limits["max_excerpt_chars"]

    pool = list(evidence)
    if query_intent == QueryIntent.QUALITATIVE:
        html = [c for c in pool if _is_html(c)]
        if html:
            if "risk" in query.lower():
                html = [
                    c
                    for c in html
                    if "risk" in c.excerpt.lower()
                    or "risk" in (c.section_id or "").lower()
                ]
            pool = sorted(html, key=lambda c: len(c.excerpt), reverse=True) or html
        pool = pool[:max_chunks]
    else:
        pool = pool[:max_chunks]

    compact: list[EvidenceChunk] = []
    for chunk in pool:
        excerpt = chunk.excerpt.strip()
        if len(excerpt) > max_chars:
            excerpt = excerpt[: max_chars - 3].rstrip() + "..."
        compact.append(chunk.model_copy(update={"excerpt": excerpt}))
    return compact


def trim_prompt_text(
    text: str,
    *,
    max_chars: int | None = None,
    budget: dict[str, int] | None = None,
) -> str:
    limit = max_chars or (budget or load_context_budget())["max_prompt_chars"]
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"


def budget_for_context_error(exc: BaseException) -> dict[str, int] | None:
    """Build a tighter budget when the server reports n_ctx in a 400 response."""
    n_ctx = _parse_n_ctx_from_error(exc)
    if n_ctx is None:
        return dict(_PROFILE_4K)
    completion = min(
        _PROFILE_4K["max_completion_tokens"],
        int(os.environ.get("LLM_MAX_COMPLETION_TOKENS", _PROFILE_4K["max_completion_tokens"])),
    )
    return derive_limits(n_ctx, completion)
