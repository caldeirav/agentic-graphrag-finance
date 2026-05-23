"""JSON parsing helpers for macro LLM output."""

from __future__ import annotations

import json

from models.enums import ComparisonMode


def extract_json_from_llm(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = stripped.find("{"), stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(stripped[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def parse_comparison_mode(value: object) -> ComparisonMode:
    if value is None:
        return ComparisonMode.YOY
    raw = str(value).strip()
    if not raw:
        return ComparisonMode.YOY
    normalized = raw.lower().replace("-", "").replace("_", "")
    if normalized in ("yoy", "yearoveryear", "yearonyear"):
        return ComparisonMode.YOY
    if normalized in ("qoq", "quarteroverquarter"):
        return ComparisonMode.QOQ
    if normalized in ("sequential", "seq", "periodoverperiod", "none"):
        return ComparisonMode.SEQUENTIAL
    try:
        return ComparisonMode(raw)
    except ValueError:
        return ComparisonMode.YOY
